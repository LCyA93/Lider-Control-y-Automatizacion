# -*- coding: utf-8 -*-
# Copyright (C) Softhealer Technologies Pvt. Ltd.
from odoo import _, fields, models
from odoo.exceptions import UserError, ValidationError


class ShQueue(models.Model):
    """A model to manage and process queue entries for third-party integrations."""
    _name = 'sh.queue'
    _description = 'Sh Queue management'

    name = fields.Char(
        string='Name',
        required=True,
        readonly=True,
    )

    remote_id = fields.Char(
        string='Remote Id',
        readonly=True
    )
    state = fields.Selection([
        ('draft', 'Draft'),
        ('error', 'Error'),
        ('done', 'Done'),
        ('delete', 'Deleted'),
    ], string="State", default='draft', copy=False)
    note = fields.Char('Note/Error', readonly=True)
    res_model = fields.Char('Res Model', readonly=True)
    res_id = fields.Char('Res id', readonly=True)

    json_data = fields.Text(
        string='Json Data',
        readonly=True,
    )

    queue_type = fields.Selection(
        string='Queue Type',
        selection=[],
        readonly=True,
    )

    sh_integration_base_id = fields.Many2one(
        string='Connector',
        comodel_name='sh.integration.config',
        readonly=True,
    )

    def _mass_action_import_from_queue(self):
        """A placeholder method for mass-importing records from the queue."""
        pass

    def action_reset_to_draft(self):
        """
        Reset queue rows from Error → Draft so they can be reprocessed
        (Import from Queue / cron).

        Only ``error`` records are moved; other states are left unchanged.
        Works for multi-selection (list Action / header button).

        Must return an action *dict* (or falsy), never ``True``: server actions
        pass the result through ``clean_action()``, which crashes on bool.
        """
        to_reset = self.filtered(lambda r: r.state == 'error')
        if not to_reset:
            raise UserError(_(
                "Only queue records in Error state can be reset to Draft. "
                "Select one or more Error rows and try again."
            ))
        # Keep previous error text in note for history; mark that it was reset.
        for rec in to_reset:
            prev_note = (rec.note or '').strip()
            note = _('Reset to Draft for retry.')
            if prev_note and not prev_note.startswith('Reset to Draft'):
                note = _('%s Previous error: %s') % (note, prev_note)
            rec.write({
                'state': 'draft',
                'note': note,
            })
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Reset to Draft'),
                'message': _(
                    '%s queue record(s) moved from Error to Draft. '
                    'You can run Import from Queue again.'
                ) % len(to_reset),
                'type': 'success',
                'sticky': False,
                'next': {'type': 'ir.actions.client', 'tag': 'soft_reload'},
            },
        }

    def reset_to_draft(self):
        """Alias used by some connectors / views (same as action_reset_to_draft)."""
        return self.action_reset_to_draft()

    def view_record(self):
        """Opens the record associated with the queue entry in a new window."""
        if self.res_model and self.res_id:
            return {
                'name': _('sh_queue_record_view'),
                'type': 'ir.actions.act_window',
                'view_mode': 'form',
                'target': 'current',
                'res_model': self.res_model,
                'res_id': int(self.res_id),
                'domain': [('id', '=', int(self.res_id))],
                'context': {'edit': True, 'create': True, 'search_default_active': 1},
            }
        else:
            raise ValidationError("res_model & res_id missing !")
