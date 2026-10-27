# -*- coding: utf-8 -*-
# Copyright (C) Softhealer Technologies Pvt. Ltd.

from odoo import http
from odoo.http import request


class MainBaseController(http.Controller):
    """A controller to handle the authorization process for third-party integrations."""
    
    def _base_error(self,content):
        """A helper method to display an error message to the user."""
        return f'''
            <h1>{content}</h1>
            '''

    @http.route('/sh_integration_base/auth/<int:res_id>', type='http', auth="public")
    def authorized_odoo_with_3rd_party_app(self,res_id,**kwargs):
        """Handles the OAuth callback from third-party applications."""
        try:
            sh_integration_config_obj = request.env['sh.integration.config'].sudo().search([
                ('id','=',res_id)
            ],limit=1)
            if sh_integration_config_obj:
                if kwargs.get("code"):
                    sh_integration_config_obj.generate_token(kwargs['code'])
                else:
                    return self._base_error(f"Failed to get the code from {sh_integration_config_obj.name} !\nkwargs: {kwargs}")
            else:
                return self._base_error(f"Failed to get the base config !\nkwargs: {kwargs}")
            return request.redirect('/')
        except Exception as e:
            return self._base_error(f"Internal Server Error: {e}")
