# -*- coding: utf-8 -*-

import os
from pydrive.auth import GoogleAuth

from odoo import http
from odoo.http import request
from odoo.tools import config



class GDriveAuth(http.Controller):


    @http.route('/google_drive/authentication', type='http', auth="public")
    def gdrive_oauth2callback(self, **kw):


        params = request.env['ir.config_parameter'].sudo()
        url_return = params.get_param('gd_backup.return_url')

        code = kw.get('code')
        settings_file = os.path.join(config["data_dir"], "GDrive", "settings.yaml")
        creds_file = os.path.join(config["data_dir"], "GDrive", "credentials.json")

        gauth = GoogleAuth(settings_file=settings_file)
        gauth.Auth(code)
        gauth.SaveCredentialsFile(creds_file)
        return request.redirect(url_return)
    

