# -*- coding: utf-8 -*-

{
    "name": "GDrive Backup",
    "version": "15.0.1",
    "summary": "Database Backup on Google Drive",
    "description": "Database Backup Upload on Google Drive",
    "license": "OPL-1",
    "author": "AISYSNEXT Ltd.",
    "website": "https://www.aisysnext.com/gd_backup",
    "category": "Administration",
    "depends": ["base"],
    "external_dependencies": {"python": ["pydrive"]},
    "data": [
        "security/ir.model.access.csv",
        "views/backup_view.xml",
        "data/backup_scheduled_action_data.xml",
    ],
    "installable": True,
    "application": False,
}
