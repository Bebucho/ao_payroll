app_name = "ao_payroll"
app_title = "Angola Payroll"
app_publisher = "AngolaERP"
app_description = "Angola Payroll Engine for ERPNext"
app_email = "jose.sardinha@2ms.co.ao"
app_license = "mit"

# Apps
# ------------------

# required_apps = []

# Each item in the list will be shown as an app in the apps page
# add_to_apps_screen = [
# 	{
# 		"name": "ao_payroll",
# 		"logo": "/assets/ao_payroll/logo.png",
# 		"title": "Angola Payroll",
# 		"route": "/ao_payroll",
# 		"has_permission": "ao_payroll.api.permission.has_app_permission"
# 	}
# ]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/ao_payroll/css/ao_payroll.css"
# app_include_js = "/assets/ao_payroll/js/ao_payroll.js"

# include js, css files in header of web template
# web_include_css = "/assets/ao_payroll/css/ao_payroll.css"
# web_include_js = "/assets/ao_payroll/js/ao_payroll.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "ao_payroll/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
# doctype_js = {"doctype" : "public/js/doctype.js"}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "ao_payroll/public/icons.svg"

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
# 	"Role": "home_page"
# }

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# Jinja
# ----------

# add methods and filters to jinja environment
# jinja = {
# 	"methods": "ao_payroll.utils.jinja_methods",
# 	"filters": "ao_payroll.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "ao_payroll.install.before_install"
# after_install = "ao_payroll.install.after_install"

# Uninstallation
# ------------

# before_uninstall = "ao_payroll.uninstall.before_uninstall"
# after_uninstall = "ao_payroll.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "ao_payroll.utils.before_app_install"
# after_app_install = "ao_payroll.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "ao_payroll.utils.before_app_uninstall"
# after_app_uninstall = "ao_payroll.utils.after_app_uninstall"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "ao_payroll.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

# permission_query_conditions = {
# 	"Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }
#
# has_permission = {
# 	"Event": "frappe.desk.doctype.event.event.has_permission",
# }

# DocType Class
# ---------------
# Override standard doctype classes

override_doctype_class = {
      "Salary Slip":
          "ao_payroll.overrides.salary_slip.AOSalarySlip",
     
       "Payroll Entry":
          "ao_payroll.overrides.payroll_entry.AOPayrollEntry",

  }

# Document Events
# ---------------
# Hook on document methods and events

# doc_events = {
# 	"*": {
# 		"on_update": "method",
# 		"on_cancel": "method",
# 		"on_trash": "method"
# 	}
# }

# Scheduled Tasks
# ---------------

scheduler_events = {
	"daily": [
		"ao_payroll.tasks.process_employee_cessations",
		"ao_payroll.tasks.process_payroll_accrual_reversals"
	]
}

# Testing
# -------

# before_tests = "ao_payroll.install.before_tests"

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "ao_payroll.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "ao_payroll.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["ao_payroll.utils.before_request"]
# after_request = ["ao_payroll.utils.after_request"]

# Job Events
# ----------
# before_job = ["ao_payroll.utils.before_job"]
# after_job = ["ao_payroll.utils.after_job"]

# User Data Protection
# --------------------

# user_data_fields = [
# 	{
# 		"doctype": "{doctype_1}",
# 		"filter_by": "{filter_by}",
# 		"redact_fields": ["{field_1}", "{field_2}"],
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_2}",
# 		"filter_by": "{filter_by}",
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_3}",
# 		"strict": False,
# 	},
# 	{
# 		"doctype": "{doctype_4}"
# 	}
# ]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
# 	"ao_payroll.auth.validate"
# ]

# Automatically update python controller files with type annotations for this app.
# export_python_type_annotations = True

# default_log_clearing_doctypes = {
# 	"Logging DocType Name": 30  # days to retain logs
# }

# Translation
# ------------
# List of apps whose translatable strings should be excluded from this app's translations.
# ignore_translatable_strings_from = []

doc_events = {
    "Journal Entry": {
        "before_cancel": "ao_payroll.journal_entry_guard.block_payroll_journal_cancellation",
    },
    "Salary Slip": {
        "validate": "ao_payroll.payroll.salary_slip.validate",
    },
    "Employee": {
        "validate": "ao_payroll.hr.employee_contract.validate_employee_contract",
    },
    "Leave Application": {
        "validate": "ao_payroll.leave_policy.validate_leave_type_active",
    },
    "Leave Allocation": {
        "validate": "ao_payroll.leave_policy.validate_leave_type_active",
    },
    "Attendance": {
        "validate": "ao_payroll.leave_policy.validate_attendance_payroll_source",
    },
    "Employee Promotion": {
        "validate": "ao_payroll.hr.employee_transactions.validate_employee_promotion",
    },
    "Employee Transfer": {
        "validate": "ao_payroll.hr.employee_transactions.validate_employee_transfer",
    },
    "Employee Onboarding": {
        "validate": "ao_payroll.hr.employee_transactions.validate_employee_onboarding",
    },
    "Employee Separation": {
        "validate": "ao_payroll.hr.employee_transactions.validate_employee_separation",
    },
}
