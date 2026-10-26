# -*- coding: utf-8 -*-
# Copyright (C) Softhealer Technologies Pvt. Ltd.

import time
from datetime import timedelta

from odoo import models, fields, api
from odoo.http import request
from odoo.addons.base.models.res_users import CryptContext
from passlib.context import CryptContext as _CryptContext

KEY_CRYPT_CONTEXT = CryptContext(
    # Low rounds acceptable here: all keys are fully random, not passwords,
    # so dictionary attacks are not a concern.
    ['pbkdf2_sha512'], pbkdf2_sha512__rounds=6000,
)


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    # ── Existing related fields (backward compatible) ──────────────────────────
    sh_powerbi_api_key = fields.Char(related='company_id.sh_powerbi_api_key', readonly=True)
    sh_powerbi_odoo_url = fields.Char(related='company_id.sh_powerbi_odoo_url', readonly=True)
    sh_powerbi_db_name = fields.Char(related='company_id.sh_powerbi_db_name', readonly=True)

    # ── New related fields (v19.0.3.0.0) ──────────────────────────────────────
    sh_powerbi_key_expiry = fields.Datetime(related='company_id.sh_powerbi_key_expiry', readonly=True)
    sh_powerbi_fetch_mode = fields.Selection(related='company_id.sh_powerbi_fetch_mode', readonly=False)
    sh_powerbi_relation_format = fields.Selection(related='company_id.sh_powerbi_relation_format', readonly=False)

    # ── Existing method — signature unchanged ──────────────────────────────────

    def action_generate_powerbi_apikey(self):
        """Generate new API key for Power BI integration."""
        for record in self:
            expiry_date = fields.Datetime.now() + timedelta(days=30)

            api_key = self.env['res.users.apikeys'].sudo()._generate(
                scope=None,
                name="Power BI Integration Key",
                expiration_date=expiry_date,
            )

            if request:
                base_url = request.httprequest.host_url.rstrip('/')
            else:
                base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
            if base_url:
                base_url = base_url + '/' if base_url[-1] != '/' else base_url

            record.company_id.write({
                'sh_powerbi_odoo_url': base_url,
                'sh_powerbi_api_key': api_key,
                'sh_powerbi_db_name': self.env.cr.dbname or '',
                'sh_powerbi_key_expiry': expiry_date,
            })

            self._log_powerbi('API key generated.', log_type='auth', state='success')

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Success!',
                    'message': 'Power BI API key generated successfully. Valid for 30 days.',
                    'type': 'success',
                },
            }

    def auth_by_apikey(self, apikey):
        """Authenticate Power BI connector using an API key.

        Return format is preserved for backward compatibility with existing .mez connector.
        """
        start = time.time()
        ip = request.httprequest.remote_addr if request else None

        self.env.cr.execute('SELECT user_id, key FROM res_users_apikeys')
        for user_id, current_key in self.env.cr.fetchall():
            if apikey and KEY_CRYPT_CONTEXT.verify(apikey, current_key):
                user = self.env['res.users'].sudo().browse(user_id)
                duration_ms = (time.time() - start) * 1000
                self._log_powerbi(
                    f'Auth success — user: {user.login}',
                    log_type='auth', state='success',
                    duration_ms=duration_ms, ip_address=ip,
                )
                return {
                    'result': {
                        'uid': user.id,
                        'login': user.login,
                        'name': user.name,
                        'db': self.env.cr.dbname,
                        'groupIds': self.env.user.group_ids.ids or [],
                    }
                }

        duration_ms = (time.time() - start) * 1000
        self._log_powerbi(
            'Auth failed — invalid API key.',
            log_type='auth', state='error', duration_ms=duration_ms, ip_address=ip,
        )
        return {'error': 'Invalid API Key'}

    def execute_powerbi_query(self, **kwargs):
        """Execute a SELECT query from Power BI.

        Return format is preserved for backward compatibility with existing .mez connector.
        """
        query = kwargs.get('query', '')
        start = time.time()
        try:
            if not query.strip().upper().startswith('SELECT'):
                return {'error': 'Only SELECT queries allowed'}
            self.env.cr.execute(query)
            result = self.env.cr.dictfetchall()

            if result:
                for row in result:
                    for key, value in row.items():
                        if isinstance(value, bytes):
                            try:
                                row[key] = value.decode('utf-8')
                            except Exception:
                                row[key] = str(value)
                        elif hasattr(value, 'isoformat'):
                            row[key] = value.isoformat()

            duration_ms = (time.time() - start) * 1000
            self._log_powerbi(
                f'Query executed successfully.',
                log_type='query', state='success',
                record_count=len(result or []), duration_ms=duration_ms,
                query_text=query[:500],
            )
            return {'result': result}
        except Exception as e:
            duration_ms = (time.time() - start) * 1000
            self._log_powerbi(
                str(e), log_type='error', state='error', duration_ms=duration_ms, query_text=query[:500],
            )
            return {'error': str(e)}

    # ── New methods (v19.0.3.0.0) ──────────────────────────────────────────────

    def action_test_powerbi_connection(self):
        """Verify the stored API key is still valid."""
        company = self.company_id
        api_key = company.sh_powerbi_api_key
        if not api_key:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {'title': 'No API Key', 'message': 'No API key found. Please generate one first.', 'type': 'warning'},
            }

        self.env.cr.execute('SELECT key FROM res_users_apikeys')
        for (current_key,) in self.env.cr.fetchall():
            if KEY_CRYPT_CONTEXT.verify(api_key, current_key):
                expiry = company.sh_powerbi_key_expiry
                expiry_str = expiry.strftime('%Y-%m-%d %H:%M') if expiry else 'Unknown'
                self._log_powerbi('Connection test: success.', log_type='auth', state='success')
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': 'Connection OK',
                        'message': f'API key is valid. Expires: {expiry_str}.',
                        'type': 'success',
                    },
                }

        self._log_powerbi('Connection test: invalid key.', log_type='auth', state='error')
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {'title': 'Connection Failed', 'message': 'API key is invalid or expired. Please generate a new one.', 'type': 'danger'},
        }

    @api.model
    @api.readonly
    def get_powerbi_settings(self):
        """Return fetch mode and company settings for the .mez connector.

        Called via /json/2/res.config.settings/get_powerbi_settings
        """
        company = self.env.company
        return {
            'fetch_mode': company.sh_powerbi_fetch_mode or 'all',
            'db': company.sh_powerbi_db_name or self.env.cr.dbname,
        }

    # ── Internal logging helper ────────────────────────────────────────────────

    def _log_powerbi(self, message, log_type='export', state='success',
                     record_count=0, duration_ms=0.0, ip_address=None, query_text=None, model_name=None):
        self.env['sh.powerbi.log'].sudo().create({
            'log_type': log_type,
            'state': state,
            'message': message,
            'record_count': record_count,
            'duration_ms': duration_ms,
            'ip_address': ip_address,
            'query_text': query_text,
            'model_name': model_name,
            'company_id': self.env.company.id,
        })
