# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt


import frappe
from frappe import _
from frappe.utils import flt

from erpnext.accounts.report.financial_statements import (
	get_pl_data,
	get_filtered_list_for_consolidated_report,
	get_period_list,
	sum_values,
	finalize_data,
)


def execute(filters=None):
	period_list = get_period_list(
		filters.from_fiscal_year,
		filters.to_fiscal_year,
		filters.period_start_date,
		filters.period_end_date,
		filters.filter_based_on,
		filters.periodicity,
		company=filters.company,
	)

	income = get_pl_data(
		filters.company,
		"Income",
		"Credit",
		period_list,
		filters=filters,
		accumulated_values=filters.accumulated_values,
		ignore_closing_entries=True,
		ignore_accumulated_values_for_fy=True,
	)

	expense_cogs = get_pl_data(
		filters.company,
		"Expense",
		"Debit",
		period_list,
		filters=filters,
		accumulated_values=filters.accumulated_values,
		ignore_closing_entries=True,
		ignore_accumulated_values_for_fy=True,
		cogs_only=True,
	)

	gross_profit_loss = get_gross_profit_loss(
		income, expense_cogs, period_list, filters.company, filters.presentation_currency
	)

	expense = get_pl_data(
		filters.company,
		"Expense",
		"Debit",
		period_list,
		filters=filters,
		accumulated_values=filters.accumulated_values,
		ignore_closing_entries=True,
		ignore_accumulated_values_for_fy=True,
	)

	operational_profit_loss = get_operational_profit_loss(
		income, expense_cogs, expense, period_list, filters.company, filters.presentation_currency
	)

	other_income = get_pl_data(
		filters.company,
		"Income",
		"Credit",
		period_list,
		filters=filters,
		accumulated_values=filters.accumulated_values,
		ignore_closing_entries=True,
		ignore_accumulated_values_for_fy=True,
		account_type="Other Income Account",
	)

	other_expense = get_pl_data(
		filters.company,
		"Expense",
		"Debit",
		period_list,
		filters=filters,
		accumulated_values=filters.accumulated_values,
		ignore_closing_entries=True,
		ignore_accumulated_values_for_fy=True,
		account_type="Other Expense Account",
	)

	non_operational_sum = get_non_operational_sum(
		other_income, other_expense, period_list, filters.company, filters.presentation_currency
	)

	net_profit_loss = get_net_profit_loss(
		income, expense, period_list, filters.company, filters.presentation_currency, other_income=other_income, other_expense=other_expense, expense_cogs=expense_cogs
	)

	data = []
	# data.extend(reorder_data(income) or [])
	# data.extend(reorder_data(expense) or [])
	# data.extend(reorder_data(other_income) or [])
	# data.extend(reorder_data(other_expense) or [])
	data.extend(income or [])
	data.extend(expense_cogs or [])

	if gross_profit_loss:
		data.append(gross_profit_loss)

	data.append({})

	data.extend(expense or [])

	if operational_profit_loss:
		data.append(operational_profit_loss)

	data.append({})

	data.append(
		{
			"name": "PENDAPATAN DAN BEBAN NON OPERASIONAL",
			"account_number": "0",
			"parent_account": "",
			"lft": 139,
			"rgt": 222,
			"root_type": "Expense",
			"report_type": "Profit and Loss",
			"account_name": "PENDAPATAN DAN BEBAN NON OPERASIONAL",
			"include_in_gross": 0,
			"account_type": "",
			"is_group": 1,
			"indent": 0,
			"opening_balance": 0
		}
	)

	data.extend(other_income or [])
	data.extend(other_expense or [])

	if non_operational_sum:
		data.append(non_operational_sum)

	data.append({})

	if net_profit_loss:
		data.append(net_profit_loss)

	columns = get_columns(
		filters.periodicity, period_list, filters.accumulated_values, filters.company
	)

	chart = get_chart_data(filters, columns, income, expense, net_profit_loss, other_income=other_income, other_expense=other_expense, expense_cogs=expense_cogs)

	currency = filters.presentation_currency or frappe.get_cached_value(
		"Company", filters.company, "default_currency"
	)
	report_summary = get_report_summary(
		period_list, filters.periodicity, income, expense,  net_profit_loss, currency, filters, other_income=other_income, other_expense=other_expense, expense_cogs=expense_cogs
	)

	data = finalize_data(data, period_list)

	return columns, data, None, chart, report_summary

def get_report_summary(
	period_list, periodicity, income, expense, net_profit_loss, currency, filters, consolidated=False, other_income=None, other_expense=None, expense_cogs=None
):
	net_income, net_expense, net_other_income, net_other_expense, net_expense_cogs, net_profit = 0.0, 0.0, 0.0, 0.0, 0.0, 0.0

	# from consolidated financial statement
	if filters.get("accumulated_in_group_company"):
		period_list = get_filtered_list_for_consolidated_report(filters, period_list)

	for period in period_list:
		key = period if consolidated else period.key

		net_income += sum_values(income, key)
		net_expense += sum_values(expense, key)
		net_expense_cogs += sum_values(expense_cogs, key)
		net_other_income += sum_values(other_income, key)
		net_other_expense += sum_values(other_expense, key)
		net_profit += net_profit_loss.get(key, 0)

	if len(period_list) == 1 and periodicity == "Yearly":
		profit_label = _("Profit This Year")
		income_label = _("Total Income This Year")
		expense_label = _("Total Expense This Year")
	else:
		profit_label = _("Net Profit")
		income_label = _("Total Income")
		expense_label = _("Total Expense")

	return [
		{"value": net_income + net_other_income, "label": income_label, "datatype": "Currency", "currency": currency},
		{"type": "separator", "value": "-"},
		{"value": net_expense + net_other_expense + net_expense_cogs, "label": expense_label, "datatype": "Currency", "currency": currency},
		{"type": "separator", "value": "=", "color": "blue"},
		{
			"value": net_profit,
			"indicator": "Green" if net_profit > 0 else "Red",
			"label": profit_label,
			"datatype": "Currency",
			"currency": currency,
		},
	]

def get_non_operational_sum(other_income, other_expense, period_list, company, currency=None, consolidated=False):
	total = 0
	non_operational_sum = {
		"account_name":  _("Jumlah Pendapatan dan Beban Non Operasional"),
		"account":  _("Jumlah Pendapatan dan Beban Non Operasional"),
		"warn_if_negative": True,
		"currency": currency or frappe.get_cached_value("Company", company, "default_currency"),
	}

	has_value = False

	for period in period_list:
		key = period if consolidated else period.key

		total_other_income = sum_values(other_income, key)
		total_other_expense = sum_values(other_expense, key)

		non_operational_sum[key] = total_other_income - total_other_expense

		if non_operational_sum[key]:
			has_value = True

		total += flt(non_operational_sum[key])
		non_operational_sum["total"] = total

	if has_value:
		return non_operational_sum

def get_gross_profit_loss(income, expense_cogs, period_list, company, currency=None, consolidated=False):
	total = 0
	gross_profit_loss = {
		"account_name": _("Laba Kotor"), 
		"account": _("Laba Kotor"),
		"warn_if_negative": True,
		"currency": currency or frappe.get_cached_value("Company", company, "default_currency"),
	}

	has_value = False

	for period in period_list:
		key = period if consolidated else period.key

		total_income = sum_values(income, key)
		total_expense_cogs = sum_values(expense_cogs, key)

		gross_profit_loss[key] = total_income - total_expense_cogs 

		if gross_profit_loss[key]:
			has_value = True

		total += flt(gross_profit_loss[key])
		gross_profit_loss["total"] = total

	if has_value:
		return gross_profit_loss

def get_operational_profit_loss(income, expense_cogs, expense, period_list, company, currency=None, consolidated=False):
	total = 0
	operational_profit_loss = {
		"account_name":  _("Laba Operasional"),
		"account":  _("Laba Operasional"),
		"warn_if_negative": True,
		"currency": currency or frappe.get_cached_value("Company", company, "default_currency"),
	}

	has_value = False

	for period in period_list:
		key = period if consolidated else period.key

		total_income = sum_values(income, key)
		total_expense_cogs = sum_values(expense_cogs, key)
		total_expense = sum_values(expense, key)

		operational_profit_loss[key] = total_income - total_expense_cogs - total_expense

		if operational_profit_loss[key]:
			has_value = True

		total += flt(operational_profit_loss[key])
		operational_profit_loss["total"] = total

	if has_value:
		return operational_profit_loss
    
def get_net_profit_loss(income, expense, period_list, company, currency=None, consolidated=False, other_income=None, other_expense=None, expense_cogs=None):
	total = 0
	net_profit_loss = {
		"account_name":  _("Laba Bersih") ,
		"account":  _("Laba Bersih"),
		"warn_if_negative": True,
		"currency": currency or frappe.get_cached_value("Company", company, "default_currency"),
	}

	has_value = False

	for period in period_list:
		key = period if consolidated else period.key

		total_income = sum_values(income, key)
		total_expense_cogs = sum_values(expense_cogs, key)
		total_expense = sum_values(expense, key)
		total_other_income = sum_values(other_income, key)
		total_other_expense = sum_values(other_expense, key)

		net_profit_loss[key] = (total_income + total_other_income) - (total_expense + total_other_expense + total_expense_cogs)

		if net_profit_loss[key]:
			has_value = True

		total += flt(net_profit_loss[key])
		net_profit_loss["total"] = total

	if has_value:
		return net_profit_loss


def get_chart_data(filters, columns, income, expense, net_profit_loss, other_income=None, other_expense=None, expense_cogs=None):
	labels = [d.get("label") for d in columns[2:]]

	income_data, expense_data, net_profit = [], [], []
	total_income, total_expense = 0.0, 0.0

	for p in columns[2:]:
		if income:
			total_income += sum_values(income, p.get("fieldname"))
		if expense:
			total_expense += sum_values(expense, p.get("fieldname"))
		if expense_cogs:
			total_expense += sum_values(expense_cogs, p.get("fieldname"))
		if other_income:
			total_income += sum_values(other_income, p.get("fieldname"))
		if other_expense:
			total_expense += sum_values(other_expense, p.get("fieldname"))
		if net_profit_loss:
			net_profit.append(net_profit_loss.get(p.get("fieldname")))
	
	income_data.append(total_income)
	expense_data.append(total_expense)

	datasets = []
	if income_data:
		datasets.append({"name": _("Income"), "values": income_data})
	if expense_data:
		datasets.append({"name": _("Expense"), "values": expense_data})
	if net_profit:
		datasets.append({"name": _("Net Profit/Loss"), "values": net_profit})

	chart = {"data": {"labels": labels, "datasets": datasets}}

	if not filters.accumulated_values:
		chart["type"] = "bar"
	else:
		chart["type"] = "line"

	chart["fieldtype"] = "Currency"

	return chart


def get_columns(periodicity, period_list, accumulated_values=1, company=None):
    columns = [
        {
            "fieldname": "account_name",
            "label": _("Account"),
            "fieldtype": "Data",
            "width": 350,
        }
    ]
    if company:
        columns.append(
            {
                "fieldname": "currency",
                "label": _("Currency"),
                "fieldtype": "Link",
                "options": "Currency",
                "hidden": 1,
            }
        )
    for period in period_list:
        columns.append(
            {
                "fieldname": period.key,
                "label": period.label,
                "fieldtype": "Data",
                "width": 250,
            }
        )

    return columns