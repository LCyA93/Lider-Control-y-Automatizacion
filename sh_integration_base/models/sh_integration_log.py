# -*- coding: utf-8 -*-
# Copyright (C) Softhealer Technologies Pvt. Ltd.

from odoo import models,fields,api


class BaseLog(models.Model):
    """A model to store log entries for third-party integrations."""
    _name = 'sh.integration.log'
    _description = 'Log'
    _order = 'id desc'


    name = fields.Char(string="Reference",default=lambda self:('New'),copy=False, readonly=True)
    description = fields.Text("Description",readonly=True)
    company_id=fields.Many2one("res.company",
                            string="Company",
                            default=lambda self: self.env.user.company_id,
                            readonly=True
                            )
    state = fields.Selection([('success','Success'),('error','Failed'),('info','Information')],readonly=True,string="State")
    config_id = fields.Many2one("sh.integration.config", string="Integration Config",readonly=True)
    response=fields.Text("Response",readonly=True)

    log_type = fields.Selection(
        string='Log Type',
        selection=[('auth', 'Authorize'), ('token', 'Token')],
        readonly=True,
    )

    def action_open_log_record(self):
        """Opens the log record in a new window."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Log Record',
            'view_mode': 'form',
            'res_model': 'sh.integration.log',
            'res_id': self.id,
            'target': 'new',
        }

    @api.model_create_multi
    def create(self, vals_list):
        """Overrides the create method to assign a unique sequence number to the log entry."""
        for vals in vals_list:
            if vals.get('name', 'New') in ('New', ('New'), False, None):
                try:
                    seq = self.env['ir.sequence'].next_by_code('sh.log.seq')
                except Exception:
                    seq = False
                vals['name'] = seq or 'New'
        return super().create(vals_list)