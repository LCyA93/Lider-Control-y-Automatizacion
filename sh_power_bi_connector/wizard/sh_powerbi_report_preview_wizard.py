# -*- coding: utf-8 -*-
# Copyright (C) Softhealer Technologies Pvt. Ltd.

from odoo import models, fields

class SHPowerBIReportPreviewWizard(models.TransientModel):
    _name = 'sh.powerbi.report.preview.wizard'
    _description = 'Power BI Report Preview Wizard'

    report_id = fields.Many2one('sh.powerbi.report')
    dashboard_id = fields.Many2one('sh.powerbi.dashboard.asset')
    embed_type = fields.Selection([('report', 'Report'), ('dashboard', 'Dashboard')], default='report')
    iframe_html = fields.Html(compute='_compute_iframe_html', sanitize=False)

    def _compute_iframe_html(self):
        for rec in self:
            if rec.embed_type == 'report' and rec.report_id:
                url = f"/sh_power_bi/embed_preview/{rec.report_id.id}?type=report"
            elif rec.embed_type == 'dashboard' and rec.dashboard_id:
                url = f"/sh_power_bi/embed_preview/{rec.dashboard_id.id}?type=dashboard"
            else:
                url = ""
                
            if url:
                rec.iframe_html = f'<iframe src="{url}" style="width:100%; height:70vh; border:none; border-radius: 8px; box-shadow: 0 4px 12px rgba(0,0,0,0.1);"></iframe>'
            else:
                rec.iframe_html = False
