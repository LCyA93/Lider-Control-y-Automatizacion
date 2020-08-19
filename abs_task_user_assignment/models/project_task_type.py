# -*- coding: utf-8 -*-
#################################################################################
#
#    Odoo, Open Source Management Solution
#    Copyright (C) 2019-today Ascetic Business Solution <www.asceticbs.com>
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
#################################################################################

from odoo import api,fields,models,_

#The Class Is Extended To Add Functionality Of Stage Assign User In Project.
class ProjectTaskType(models.Model):
    _inherit = 'project.task.type'

    #For Add The Functionality Of Stage Assign User In New Stage Record.
    @api.model
    def create(self,vals):
        variable=super(ProjectTaskType, self).create(vals)
        if vals.get('project_ids', False):
            projects_id = vals.get('project_ids')
            if projects_id:
                project_list_ids = projects_id[0][2]
                for project in project_list_ids:
                    self.env['stage.user'].create({'project_id':project,'stage_id':variable.id})           
        return variable 

    #For Add New Functionality  Of Stage Assign User In Existing Stage Record.
    @api.multi
    def write(self,vals):
        if vals.get('project_ids'):
            projects_id = vals.get('project_ids', False)
            project_list_ids = projects_id[0][2]
            for project in project_list_ids:
                stage_project_id =  self.env['stage.user'].search([('project_id','=',project),('stage_id','=',self.id)])
                if stage_project_id:
                    pass
                else:
                    self.env['stage.user'].create({'project_id':project,'stage_id':self.id})
            stage_project_id =  self.env['stage.user'].search([('project_id','not in',project_list_ids),('stage_id','=',self.id)])
            if stage_project_id:
                stage_project_id.unlink() 
        return super(ProjectTaskType, self).write(vals)


#The Class Is Extended To Add Functionality Of Stage Assign User In Task Of Project.
class Task(models.Model):
    _inherit = 'project.task'

    #For Add New The Functionality  Of Stage Assign User In Existing Task Record At A Time Of Stage Cahnge.
    @api.multi
    def write(self,vals):
        if vals.get('stage_id', False):
            for record in self:
                users_id = 0
                if record.project_id:   
                    stage_user_ids =  self.env['stage.user'].search([('project_id','=',record.project_id.id),('stage_id','=',vals['stage_id'])])
                    if stage_user_ids:
                        users_id= stage_user_ids[0].user_id.id
                        vals['user_id'] = users_id
        return super(Task, self).write(vals)
