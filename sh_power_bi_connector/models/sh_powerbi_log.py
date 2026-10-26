# -*- coding: utf-8 -*-
# Copyright (C) Softhealer Technologies Pvt. Ltd.

from odoo import models, fields, api


class SHPowerBILog(models.Model):
    _name = 'sh.powerbi.log'
    _description = 'Power BI Audit Log'
    _order = 'id desc'

    name = fields.Char(string='Reference', readonly=True, copy=False)
    log_type = fields.Selection([
        ('auth', 'Authentication'),
        ('query', 'Query Execution'),
        ('export', 'Data Export'),
        ('push', 'Data Push'),
        ('error', 'Error'),
    ], string='Event Type', required=True, default='export')
    state = fields.Selection([
        ('success', 'Success'),
        ('error', 'Failed'),
    ], string='Status', required=True, default='success')
    message = fields.Text(string='Message')
    datetime = fields.Datetime(string='Date & Time', default=fields.Datetime.now, readonly=True)
    query_text = fields.Text(string='Query')
    model_name = fields.Char(string='Model')
    record_count = fields.Integer(string='Records')
    duration_ms = fields.Float(string='Duration (ms)', digits=(10, 2))
    ip_address = fields.Char(string='Client IP')
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name'):
                vals['name'] = self.env['ir.sequence'].next_by_code('sh.powerbi.log') or 'PBI/00001'
        return super().create(vals_list)
