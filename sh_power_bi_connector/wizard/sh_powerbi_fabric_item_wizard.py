# -*- coding: utf-8 -*-
# Copyright (C) Softhealer Technologies Pvt. Ltd.

from odoo import models, fields, _
from odoo.exceptions import UserError
import json


class SHPowerBIFabricItemWizard(models.TransientModel):
    """Wizard to create a new Fabric Item."""

    _name = 'sh.powerbi.fabric.item.wizard'
    _description = 'Create Fabric Item Wizard'

    fabric_config_id = fields.Many2one('sh.powerbi.fabric.config', string='Fabric Configuration', required=True)
    name = fields.Char(string='Item Name', required=True)
    item_type = fields.Selection([
        ('Lakehouse', 'Lakehouse'),
        ('Warehouse', 'Warehouse'),
        ('Eventhouse', 'Eventhouse'),
        ('KQLDatabase', 'KQL Database'),
        ('DataPipeline', 'Data Pipeline'),
        ('CopyJob', 'Copy Job'),
    ], string='Item Type', default='Lakehouse', required=True)
    description = fields.Text(string='Description')

    def action_create_item(self):
        self.ensure_one()
        config = self.fabric_config_id
        if not config.workspace_id:
            raise UserError(_("Please discover or set a workspace on the configuration first."))

        payload = {
            "displayName": self.name,
            "type": self.item_type
        }
        if self.description:
            payload["description"] = self.description

        success, result = config._make_fabric_request('POST', f'workspaces/{config.workspace_id}/items', data=payload)
        if not success:
            config._log_fabric(_("Failed to create Fabric item '%s': %s") % (self.name, result), state='error')
            raise UserError(_("Failed to create Fabric item: %s") % result)

        config._log_fabric(_("Successfully created Fabric item '%s' (%s).") % (self.name, self.item_type))
        
        # Trigger background discovery
        config.action_discover_items()

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Success'),
                'message': _('Fabric item created successfully and synced with Odoo.'),
                'type': 'success',
                'next': {'type': 'ir.actions.client', 'tag': 'reload'},
            }
        }
