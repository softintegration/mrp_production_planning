# -*- coding: utf-8 -*- 


{
 'name': 'Manufacturing planning',
 'author': 'Soft-integration',
 'application': False,
 'installable': True,
 'auto_install': False,
 'qweb': [],
 'description': False,
 'images': [],
 'version': '1.0.2.12',
 'category': 'Manufacturing/Manufacturing',
 'demo': [],
 'depends': ['mrp_production_request','record_scheduling'],
 'data': [
     'security/mrp_production_planning_security.xml',
     'security/ir.model.access.csv',
     'data/mrp_production_planning_data.xml',
     'views/mrp_production_planning_views.xml',
     'views/scheduling_rule_views.xml',
     'views/mrp_workorder_views.xml',
     'views/mrp_production_request_views.xml',
     'views/mrp_production_views.xml',
     'views/res_config_settings_views.xml'
    ],
 'license': 'LGPL-3',
 }