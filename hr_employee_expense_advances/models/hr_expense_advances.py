# -*- coding: utf-8 -*-
###############################################################################
#    License, author and contributors information in:                         #
#    __manifest__.py file at the root folder of this module.                  #
###############################################################################

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
import odoo.addons.decimal_precision as dp

class HrExpenseAdvances(models.Model):    
    _name = "hr.expense.advances"
    _description = "Expense Advances"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _mail_post_access = 'read'

    def _default_employee(self):
        return self.env['hr.employee'].search([('user_id', '=', self.env.uid)], limit=1)

    name = fields.Char(readonly=True, copy=False, default="Draft Expense Advance") # The name is attributed upon post()
    employee_id = fields.Many2one('hr.employee', string="Employee Name", required=True,default=_default_employee)
    department_id = fields.Many2one('hr.department',string="Department Name")    
    job_id = fields.Many2one('hr.job',string="Job Title")
    requested_date = fields.Date(string='Requested Date',default=fields.Date.context_today)    
    requested_user = fields.Many2one('res.users', string="Requested User",default=lambda self: self.env.user.id)
    requested_amount = fields.Float(string='Requested Amount', required=True, digits=dp.get_precision('Requested Amount'))
    currency_id = fields.Many2one('res.currency', string='Currency', default=lambda self: self.env.user.company_id.currency_id,domain=[('name', '=', 'AED')])
    
    journal_id = fields.Many2one('account.journal', string='Payment Method',domain=[('type', 'in', ('bank', 'cash'))])
    advance_account = fields.Many2one('account.account',string='Advance Account')
    payment_date = fields.Date(string='Paid Date',default=fields.Date.context_today)
    paid_amount = fields.Float(string='Paid Amount',digits=dp.get_precision('Paid Amount'))
    move_id = fields.Many2one('account.move',string='Journal Entry')
    note = fields.Text('Reason / Notes')

    state = fields.Selection([
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('paid', 'Paid'),
        ],default='draft',string='Status', copy=False, index=True, readonly=True, store=True,track_visibility='always',
        help="Status of the expense advance.")
    
    #create inherit function
    @api.model
    def create(self, vals):
        result = super(HrExpenseAdvances,self).create(vals)        
        group_id = self.env['ir.model.data'].xmlid_to_res_id('hr_expense.group_hr_expense_manager')
        hr_expense_managers = self.get_users_from_group(group_id)
        if hr_expense_managers:
            result.message_subscribe(partner_ids=hr_expense_managers)        
        body =_("Expense Advance Created")
        subject = _("Expense Advance")
        result.message_post(body=body, subject=subject,message_type="notification", subtype="mail.mt_comment",)
        return result
    
    #passing group id using self.env['ir.model.data'].xmlid_to_res_id('hr_expense.group_hr_expense_manager')
    @api.multi
    def get_users_from_group(self,group_id):
        users_ids = []
        sql_query = """select uid from res_groups_users_rel where gid = %s"""                
        params = (group_id,)
        self.env.cr.execute(sql_query, params)
        results = self.env.cr.fetchall()
        for users_id in results:
            users_ids.append(users_id[0])
        return users_ids
    
    #other validations
    @api.onchange('employee_id')
    def onchnage_employee_id(self):
        self.department_id = self.employee_id.department_id.id
        self.job_id = self.employee_id.job_id.id

    @api.onchange('requested_amount')
    def onchnage_requested_amount(self):
        self.paid_amount = self.requested_amount
        
    @api.multi
    @api.constrains('requested_amount','paid_amount')
    def check_requested_amount(self):
        if self.requested_amount <= 0.00:
            raise ValidationError(_("The requested amount should be greter than  0.0!"))
        
        if self.paid_amount <= 0.00:
            raise ValidationError(_("The paid amount should be greter than  0.0!"))

    #onboarding workflow
    @api.multi
    def action_draft(self):
        self.state = 'draft'

    @api.multi
    def action_submit(self):        
        self.state = 'submitted'
        body =_("Expense Advance Submitted")
        subject = _("Expense Advance")
        self.message_post(body=body, subject=subject,message_type="notification", subtype="mail.mt_comment",)  

    #Posting journal entries
    @api.multi
    def action_done(self):
        for rec in self:
            debit = credit = rec.currency_id.compute(rec.paid_amount, rec.currency_id)           
            
            if not self.user_has_groups('hr_expense.group_hr_expense_manager'):
                raise ValidationError("You cannot paid expense advance of employee.")

            if rec.state == 'draft':
                raise UserError(_("Only a Submitted payment can be posted. Trying to post a payment in state %s.") % rec.state)
            
            if not rec.journal_id:
                raise ValidationError("Please select Payment Method")

            if not rec.advance_account:
                raise ValidationError("Please select Advance Account")

            sequence_code = 'hr.advance.sequence'
            rec.name = self.env['ir.sequence'].with_context(ir_sequence_date=rec.payment_date).next_by_code(sequence_code)
            
            move = {
                'name': '/',
                'journal_id': rec.journal_id.id,
                'date': rec.payment_date,

                'line_ids': [(0, 0, {
                        'name': rec.name or '/',
                        'debit': debit,
                        'account_id': rec.advance_account.id,
                        'partner_id': rec.employee_id.user_id.partner_id.id,
                    }), (0, 0, {
                        'name': rec.name or '/',
                        'credit': credit,
                        'account_id': rec.journal_id.default_credit_account_id.id,
                        'partner_id': rec.employee_id.user_id.partner_id.id,
                    })]
            }
            move_id = self.env['account.move'].create(move)
            move_id.post()
            body =_("Expense Advance Paid")
            subject = _("Expense Advance - %s") % (rec.name,)
            rec.message_post(body=body, subject=subject,message_type="notification", subtype="mail.mt_comment",)
            return rec.write({'state': 'paid', 'move_id': move_id.id})
            
