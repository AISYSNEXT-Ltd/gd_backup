# -*- coding: utf-8 -*-

import logging


from pydrive.auth import GoogleAuth
from pydrive.drive import GoogleDrive
import yaml

import odoo
from odoo import models, fields, _, exceptions
from odoo.tools import config
from odoo.http import request


_logger = logging.getLogger(__name__)
import os
import glob
import datetime




class Backup(models.Model):
    _name = "db.backup"
    _description = "Backup record"

    database = fields.Char(string="Database", required=True)
    date_backup = fields.Datetime(string="Backup Date", default=fields.Datetime.now())
    drive_folder = fields.Char(string="Drive Folder", required=True)
    actor = fields.Selection(
        [("auto", "Automatic"), ("manual", "Manual")],
        string="Actor of backup",
        default="auto",
        required=True,
    )


class GDrive(models.TransientModel):
    _name = "db.gdrive"
    _description = "Google Drive model"
    _env = {}
    is_auth = fields.Boolean(string="Google Drive is auth or not", default=False)

    def _init_env(self):
        params = self.env["ir.config_parameter"].sudo()
        self._env["drive_folder_id"] = params.get_param("gd_backup.drive_folder_id")
        self._env["drive_client_id"] = params.get_param("gd_backup.drive_client_id")
        self._env["drive_client_secret"] = params.get_param(
            "gd_backup.drive_client_secret"
        )
        self._env["master_pwd"] = params.get_param("gd_backup.master_pwd")
        self._env["backup_format"] = params.get_param("gd_backup.backup_format")
        self._env["gdrive_upload"] = params.get_param("gd_backup.gdrive_upload")
        self.is_auth = False

    def init(self, scopes=[]) -> None:
        self._init_env()

        if not os.path.exists(
            os.path.join(config["data_dir"], "GDrive", "settings.yaml")
        ):
            if not os.path.exists(os.path.join(config["data_dir"], "GDrive")):
                os.mkdir(os.path.join(config["data_dir"], "GDrive"))

            if scopes:
                self.create_setting_file(scopes)
            else:
                self.create_setting_file()

    def create_setting_file(
        self,
        scopes=[
            "https://www.googleapis.com/auth/drive",
            "https://www.googleapis.com/auth/drive.file",
            "https://www.googleapis.com/auth/drive.install",
        ],
    ):
        data = {
            "client_config_backend": "settings",
            "client_config": {
                "client_id": str(self._env["drive_client_id"]),
                "client_secret": str(self._env["drive_client_secret"]),
                "redirect_uri": str(request.env["ir.config_parameter"].get_param(
                    "web.base.url"
                ))
                + "/google_drive/authentication",
            },
            "oauth_scope": scopes,
        }

        with open(
            os.path.join(config["data_dir"], "GDrive", "settings.yaml"),
            "w",
            encoding="utf8",
        ) as f:
            yaml.dump(data, f)

    def auth(self):
        self.init()

        gauth = GoogleAuth(
            settings_file=os.path.join(config["data_dir"], "GDrive", "settings.yaml")
        )

        if os.path.exists(
            os.path.join(config["data_dir"], "GDrive", "credentials.json")
        ):
            gauth.LoadCredentialsFile(
                os.path.join(config["data_dir"], "GDrive", "credentials.json")
            )

        if gauth.access_token_expired:
            return self.generate_code(gauth)

        self.is_auth = True

        return self.is_auth

    def generate_code(self, gauth):
        auth_url = gauth.GetAuthUrl()

        return {"type": "ir.actions.act_url", "target": "self", "url": auth_url}

    def upload(self, backup_path):
        if os.path.exists(backup_path):
            gauth = GoogleAuth(
                settings_file=os.path.join(
                    config["data_dir"], "GDrive", "settings.yaml"
                )
            )

            if os.path.exists(
                os.path.join(config["data_dir"], "GDrive", "credentials.json")
            ):
                gauth.LoadCredentialsFile(
                    os.path.join(config["data_dir"], "GDrive", "credentials.json")
                )

            if gauth.access_token_expired:
                return self.generate_code(gauth)

            drive = GoogleDrive(gauth)

            backup_file = drive.CreateFile(
                {
                    "parents": [{"id": self._env["drive_folder_id"]}],
                    "title": os.path.basename(backup_path).split("/")[-1],
                }
            )

            backup_file.SetContentFile(backup_path)
            backup_file.Upload()

        else:
            raise exceptions.UserError(
                "Backup Folder not exist please check you backup configuration!"
            )

    def create_backup(self):
        backup_time = datetime.datetime.utcnow().strftime("%Y-%m-%d_%H-%M-%S")
        backup_base_path = os.path.join(config["data_dir"], "GDrive", "backup")

        files = []

        if not os.path.isdir(backup_base_path):
            os.makedirs(backup_base_path)

        for database in odoo.service.db.list_dbs():
            backup_filename = "%s_%s.%s" % (
                database,
                backup_time,
                self._env["backup_format"],
            )
            backup_path = os.path.join(backup_base_path, backup_filename)

            f = open(backup_path, "wb")
            odoo.service.db.dump_db(database, f, self._env["backup_format"])
            f.close()

            files.append(backup_path)

        return files

    def schedule_backup(self, cron=False):
        self._init_env()
        self._check_db_creds()

        dbs = self.create_backup()
        rec = self.env["db.backup"]

        for db in dbs:
            self.upload(db)
            if cron:
                rec.create(
                    {
                        "database": db,
                        "drive_folder": self._env["drive_folder_id"],
                        "actor": "auto",
                    }
                )
            else:
                rec.create(
                    {
                        "database": db,
                        "drive_folder": self._env["drive_folder_id"],
                        "actor": "manual",
                    }
                )

    def _check_db_creds(self):
        try:
            odoo.service.db.check_super(self._env["master_pwd"])
        except Exception:
            raise exceptions.ValidationError(_("Invalid Master password!"))

    def _clean_backup_folder(self):
        files = glob.glob(os.path.join(config["data_dir"], "GDrive", "backup") + "/*")
        for f in files:
            os.remove(f)


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    gdrive_upload = fields.Boolean("Upload to Google Drive")
    drive_folder_id = fields.Char(string="Folder ID", required=True)
    drive_client_id = fields.Char(string="Google Drive client_id", required=True)
    drive_client_secret = fields.Char(
        string="Google Drive client_secret", required=True
    )

    return_url = fields.Char(string="Return URL", required=True, default="/web")

    master_pwd = fields.Char(string="Master Password", required=True)
    backup_format = fields.Selection(
        [("zip", "Zip"), ("dump", "Dump")],
        string="Backup Format",
        default="zip",
        required=True,
    )

    def set_values(self):
        res = super(ResConfigSettings, self).set_values()

        self.env["ir.config_parameter"].set_param(
            "gd_backup.gdrive_upload", self.gdrive_upload
        )

        self.env["ir.config_parameter"].set_param(
            "gd_backup.drive_folder_id", self.drive_folder_id
        )

        self.env["ir.config_parameter"].set_param(
            "gd_backup.drive_client_id", self.drive_client_id
        )

        self.env["ir.config_parameter"].set_param(
            "gd_backup.drive_client_secret", self.drive_client_secret
        )

        self.env["ir.config_parameter"].set_param(
            "gd_backup.master_pwd", self.master_pwd
        )

        self.env["ir.config_parameter"].set_param(
            "gd_backup.backup_format", self.backup_format
        )

        self.env["ir.config_parameter"].set_param(
            "gd_backup.return_url", self.return_url
        )

        return res

    def get_values(self):
        res = super(ResConfigSettings, self).get_values()
        values = self.env["ir.config_parameter"].sudo()

        res.update(
            gdrive_upload=values.get_param("gd_backup.gdrive_upload"),
            drive_folder_id=values.get_param("gd_backup.drive_folder_id"),
            drive_client_id=values.get_param("gd_backup.drive_client_id"),
            drive_client_secret=values.get_param("gd_backup.drive_client_secret"),
            master_pwd=values.get_param("gd_backup.master_pwd"),
            backup_format=values.get_param("gd_backup.backup_format"),
            return_url=values.get_param("gd_backup.return_url"),
        )
        return res

    def generate_token(self):
        drive = self.env["db.gdrive"]

        re = drive.auth()

        if isinstance(re, bool):
            if re:
                return {
                    "type": "ir.actions.client",
                    "tag": "display_notification",
                    "params": {
                        "title": _("Connection Google Drive"),
                        "type": "success",
                        "message": _("your connection is ok"),
                        "sticky": False,
                    },
                }
            else:
                return {
                    "type": "ir.actions.client",
                    "tag": "display_notification",
                    "params": {
                        "title": _("Connection Google Drive"),
                        "type": "error",
                        "message": "check your client_id or client_secret or folder id  !",
                        "sticky": False,
                    },
                }

        else:
            return re

    def manual_backup(self):
        drive = self.env["db.gdrive"]
        drive.schedule_backup()

    def clean_backup(self):
        drive = self.env["db.gdrive"]
        drive._clean_backup_folder()
