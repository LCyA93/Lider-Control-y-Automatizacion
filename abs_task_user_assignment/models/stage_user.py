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

#New Class Is Created For Stage Assign User 
class StageUser(models.Model):
    _name='stage.user'
   
    stage_id = fields.Many2one('project.task.type', string='Stage', readonly=True, help="Many2one Field Related To Project Task Type")
    user_id = fields.Many2one('res.users', string='Assign To', help="Many2one Field Related To res user")
    project_id = fields.Many2one('project.project', string="Project", help="Many2one Field Related To Project")


