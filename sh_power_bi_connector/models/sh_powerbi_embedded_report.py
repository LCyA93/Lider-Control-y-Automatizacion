# -*- coding: utf-8 -*-
# Copyright (C) Softhealer Technologies Pvt. Ltd.

import logging
from datetime import timedelta

import requests

from odoo import models, fields, api
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

EMBED_TOKEN_TIMEOUT = 30


class SHPowerBIEmbeddedReport(models.Model):
    _name = 'sh.powerbi.embedded.report'
    _description = 'Power BI Embedded Report'
    _order = 'name'

    name = fields.Char(string='Report Name', required=True)
    push_config_id = fields.Many2one(
        'sh.powerbi.push.config',
        string='Push Configuration',
        required=True,
        help="Reuses Azure AD credentials from this Push Configuration.",
    )
    company_id = fields.Many2one(
        'res.company', string='Company', required=True,
        default=lambda self: self.env.company,
    )
    report_id = fields.Char(
        string='Power BI Report ID',
        help="GUID of the report — found in the Power BI report URL after /reports/",
    )
    workspace_id = fields.Char(
        string='Workspace ID',
        help="GUID of the Power BI workspace. Defaults to the Push Configuration workspace if blank.",
    )
    embed_url = fields.Char(string='Embed URL', readonly=True, copy=False)
    embed_token = fields.Char(string='Embed Token', readonly=True, copy=False)
    token_expiry = fields.Datetime(string='Token Expiry', readonly=True, copy=False)
    is_active = fields.Boolean(string='Active', default=True)
    allow_embedding = fields.Boolean(
        string='Allow Embedding',
        default=True,
        help="When enabled, the report is displayed as an embedded iframe inside Odoo.",
    )
    last_sync_date = fields.Datetime(string='Last Data Refresh', readonly=True, copy=False)
    web_url = fields.Char(string='Power BI Web URL', readonly=True, copy=False)
    report_status = fields.Selection([
        ('live', 'Live & Syncing'),
        ('expired', 'Token Expired'),
        ('no_token', 'No Token'),
        ('inactive', 'Inactive'),
    ], string='Report Status', compute='_compute_report_status', store=False)

    def _get_effective_workspace_id(self):
        self.ensure_one()
        return (self.workspace_id or self.push_config_id.powerbi_workspace_id or '').strip()

    @api.depends('token_expiry', 'embed_token', 'is_active')
    def _compute_report_status(self):
        now = fields.Datetime.now()
        for rec in self:
            if not rec.is_active:
                rec.report_status = 'inactive'
            elif not rec.embed_token:
                rec.report_status = 'no_token'
            elif rec.token_expiry and now >= rec.token_expiry:
                rec.report_status = 'expired'
            else:
                rec.report_status = 'live'

    # kept for backward compat
    token_status = fields.Selection([
        ('none', 'No Token'),
        ('valid', 'Valid'),
        ('expired', 'Expired'),
    ], string='Token Status', compute='_compute_token_status', store=False)

    @api.depends('token_expiry')
    def _compute_token_status(self):
        now = fields.Datetime.now()
        for rec in self:
            if not rec.token_expiry:
                rec.token_status = 'none'
            elif now >= rec.token_expiry:
                rec.token_status = 'expired'
            else:
                rec.token_status = 'valid'

    def action_generate_embed_token(self):
        """Fetch an embed token from Power BI for this report."""
        self.ensure_one()
        if not self.report_id:
            raise UserError("Please set a Power BI Report ID before generating an embed token.")
        workspace_id = self._get_effective_workspace_id()
        if not workspace_id:
            raise UserError("Please set a Workspace ID (or configure one on the Push Configuration).")

        config = self.push_config_id
        config._refresh_token_if_needed()

        # Also fetch the web URL for "Open in Power BI" button
        report_api_url = (
            f"https://api.powerbi.com/v1.0/myorg/groups/{workspace_id}"
            f"/reports/{self.report_id}"
        )
        headers = {
            'Authorization': f'Bearer {config.powerbi_access_token}',
            'Content-Type': 'application/json',
        }
        try:
            meta_resp = requests.get(report_api_url, headers=headers, timeout=EMBED_TOKEN_TIMEOUT)
            meta = meta_resp.json() if meta_resp.status_code == 200 else {}
        except Exception:
            meta = {}

        url = (
            f"https://api.powerbi.com/v1.0/myorg/groups/{workspace_id}"
            f"/reports/{self.report_id}/GenerateToken"
        )
        try:
            resp = requests.post(
                url,
                headers=headers,
                json={'accessLevel': 'View'},
                timeout=EMBED_TOKEN_TIMEOUT,
            )
        except requests.exceptions.RequestException as e:
            raise UserError(f"Embed token request failed: {e}") from e

        if resp.status_code not in (200, 201):
            try:
                err = resp.json().get('error', {}).get('message') or resp.text
            except Exception:
                err = resp.text
            raise UserError(f"Failed to generate embed token: {err}")

        data = resp.json()
        embed_url = meta.get('embedUrl') or data.get('embedUrl', '')
        token = data.get('token', '')
        expiry_str = data.get('expiration', '')
        try:
            from datetime import datetime as _dt
            expiry = _dt.strptime(expiry_str, '%Y-%m-%dT%H:%M:%SZ') if expiry_str else (
                fields.Datetime.now() + timedelta(hours=1)
            )
        except Exception:
            expiry = fields.Datetime.now() + timedelta(hours=1)

        self.write({
            'embed_url': embed_url,
            'embed_token': token,
            'token_expiry': expiry,
            'last_sync_date': fields.Datetime.now(),
            'web_url': meta.get('webUrl', ''),
        })
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Token Generated',
                'message': 'Embed token generated successfully.',
                'type': 'success',
                'next': {'type': 'ir.actions.client', 'tag': 'reload'},
            },
        }

    def action_view_report(self):
        """Open the embedded Power BI report iframe inside Odoo."""
        self.ensure_one()
        if not self.embed_url or not self.embed_token:
            raise UserError("Please generate an embed token first.")
        if self.token_expiry and fields.Datetime.now() >= self.token_expiry:
            raise UserError(
                "The embed token has expired. Please click 'Generate Token' to refresh it."
            )
        return {
            'type': 'ir.actions.act_url',
            'url': f'/sh_power_bi/embed/{self.id}',
            'target': 'new',
        }

    def action_open_in_powerbi(self):
        """Open the report directly in app.powerbi.com."""
        self.ensure_one()
        workspace_id = self._get_effective_workspace_id()
        url = (
            self.web_url or
            f"https://app.powerbi.com/groups/{workspace_id}/reports/{self.report_id}"
        )
        return {
            'type': 'ir.actions.act_url',
            'url': url,
            'target': 'new',
        }
