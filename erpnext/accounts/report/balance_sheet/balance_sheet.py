# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt


import frappe
from frappe import _
from frappe.utils import cint, flt

from erpnext.accounts.report.financial_statements import (
    get_bs_data,
    get_filtered_list_for_consolidated_report,
    get_period_list,
    add_summary_dict,
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

    filters.period_start_date = period_list[0]["year_start_date"].replace(month=1, day=1)

    currency = filters.presentation_currency or frappe.get_cached_value(
        "Company", filters.company, "default_currency"
    )

    kas_setara_kas = get_bs_data(
        filters.company,
        "Asset",
        "Debit",
        period_list,
        only_current_fiscal_year=False,
        filters=filters,
        accumulated_values=filters.accumulated_values,
		sub_account_type='Cash Account'
    )

    piutang_usaha = get_bs_data(
        filters.company,
        "Asset",
        "Debit",
        period_list,
        only_current_fiscal_year=False,
        filters=filters,
		sub_account_type='Receivable Account'
    )

    persediaan = get_bs_data(
        filters.company,
        "Asset",
        "Debit",
        period_list,
        only_current_fiscal_year=False,
        filters=filters,
        accumulated_values=filters.accumulated_values,
		sub_account_type='Inventory Account'
    )

    aset_lancar_lainnya = get_bs_data(
        filters.company,
        "Asset",
        "Debit",
        period_list,
        only_current_fiscal_year=False,
        filters=filters,
        accumulated_values=filters.accumulated_values,
		sub_account_type='Other Current Asset Account'
    )

    nilai_histori = get_bs_data(
        filters.company,
        "Asset",
        "Debit",
        period_list,
        only_current_fiscal_year=False,
        filters=filters,
        accumulated_values=filters.accumulated_values,
		sub_account_type='Fixed Asset Account'
	)

    akumulasi_penyusutan = get_bs_data(
        filters.company,
        "Asset",
        "Debit",
        period_list,
        only_current_fiscal_year=False,
        filters=filters,
        accumulated_values=filters.accumulated_values,
		sub_account_type='Accumulated Depreciation Account'
    )

    utang_usaha = get_bs_data(
        filters.company,
        "Liability",
        "Credit",
        period_list,
        only_current_fiscal_year=False,
        filters=filters,
        accumulated_values=filters.accumulated_values,
		sub_account_type='Business Liability Account'
    )

    kewajiban_jangka_pendek_lainnya = get_bs_data(
        filters.company,
        "Liability",
        "Credit",
        period_list,
        only_current_fiscal_year=False,
        filters=filters,
        accumulated_values=filters.accumulated_values,
		sub_account_type='Other Current Liability Account'
    )

    equity = get_bs_data(
        filters.company,
        "Equity",
        "Credit",
        period_list,
        only_current_fiscal_year=False,
        filters=filters,
        accumulated_values=filters.accumulated_values,
		sub_account_type='Equity Account'
    )

    provisional_profit_loss, total_credit = get_provisional_profit_loss(
        kas_setara_kas, piutang_usaha, persediaan, aset_lancar_lainnya, nilai_histori, akumulasi_penyusutan, utang_usaha, kewajiban_jangka_pendek_lainnya, equity,
        period_list, filters.company, currency
    )

    equity = organize_equity_data(equity, provisional_profit_loss, period_list)

    aset_lancar = sum_aset_lancar(
        kas_setara_kas, piutang_usaha, persediaan, aset_lancar_lainnya, period_list, filters.company, currency)

    aset_tidak_lancar = sum_aset_tidak_lancar(
        nilai_histori, akumulasi_penyusutan, period_list, filters.company, currency)
    
    total_aset = sum_all_asset(kas_setara_kas, piutang_usaha, persediaan, aset_lancar_lainnya,
                            nilai_histori, akumulasi_penyusutan, period_list, filters.company, currency)


    kewajiban_jangka_pendek = sum_kewajiban_jangka_pendek(
        utang_usaha, kewajiban_jangka_pendek_lainnya, period_list, filters.company, currency)

    kewajiban = sum_kewajiban(
        utang_usaha, kewajiban_jangka_pendek_lainnya, period_list, filters.company, currency)

    liabilitas_dan_ekuitas = sum_liabilitas_dan_ekuitas(
        utang_usaha, kewajiban_jangka_pendek_lainnya, equity, period_list, filters.company, currency)

    message, opening_balance = check_opening_balance(
        kas_setara_kas, piutang_usaha, persediaan, aset_lancar_lainnya, nilai_histori, akumulasi_penyusutan, utang_usaha, kewajiban_jangka_pendek_lainnya, equity,
    )

    data = []
    data.append(add_summary_dict(_("ASET"), 1, 1, "Asset"))
    data.append(add_summary_dict(_("ASET LANCAR"), 1, 1, "Asset"))
    data.extend(kas_setara_kas or [])
    data.extend(piutang_usaha or [])
    data.extend(persediaan or [])
    data.extend(aset_lancar_lainnya or [])

    if aset_lancar:
        data.append(aset_lancar)

    data.append({})

    data.append(add_summary_dict(_("ASET TIDAK LANCAR"), 1, 1, "Asset"))
    data.extend(nilai_histori or [])
    data.extend(akumulasi_penyusutan or [])

    if aset_tidak_lancar:
        data.append(aset_tidak_lancar)

    data.append({})

    if total_aset:
        data.append(total_aset)

    data.append({})

    data.append(add_summary_dict(
        _("LIABILITAS DAN EKUITAS"), 1, 1, "Liability"))
    data.append(add_summary_dict(_("LIABILITAS"), 1, 1, "Liability"))
    data.append(add_summary_dict(
        _("LIABILITAS JANGKA PENDEK"), 1, 1, "Liability"))
    data.extend(utang_usaha or [])
    data.extend(kewajiban_jangka_pendek_lainnya or [])

    if kewajiban_jangka_pendek:
        data.append(kewajiban_jangka_pendek)

    data.append({})

    if kewajiban:
        data.append(kewajiban)

    data.append({})

    data.extend(equity or [])

    if liabilitas_dan_ekuitas:
        data.append(liabilitas_dan_ekuitas)

    if opening_balance and round(opening_balance, 2) != 0:
        unclosed = {
            "account_name": "'" + _("Unclosed Fiscal Years Profit / Loss (Credit)") + "'",
            "account": "'" + _("Unclosed Fiscal Years Profit / Loss (Credit)") + "'",
            "warn_if_negative": True,
            "currency": currency,
        }
        for period in period_list:
            unclosed[period.key] = opening_balance
            if provisional_profit_loss:
                provisional_profit_loss[period.key] = provisional_profit_loss[period.key] - opening_balance

        unclosed["total"] = opening_balance
        data.append(unclosed)

    columns = get_columns(
        filters.periodicity, period_list, filters.accumulated_values, company=filters.company
    )

    chart = get_chart_data(
        filters, columns,
        kas_setara_kas, piutang_usaha, persediaan, aset_lancar_lainnya, nilai_histori, akumulasi_penyusutan, utang_usaha, kewajiban_jangka_pendek_lainnya, equity,
    )

    report_summary = get_report_summary(
        period_list, kas_setara_kas, piutang_usaha, persediaan, aset_lancar_lainnya, nilai_histori, akumulasi_penyusutan, utang_usaha, kewajiban_jangka_pendek_lainnya, equity, provisional_profit_loss, currency, filters
    )

    data = finalize_data(data, period_list)

    return columns, data, message, chart, report_summary

def organize_equity_data(equity, provisional_profit_loss, period_list, consolidated=False):
    for period in period_list:
        # Determine the key based on the consolidated flag
        key = period if consolidated else period['key']

        # Create the 'laba_tahun_ini' object
        first_item = equity[1]
        laba_tahun_ini = {
            "account_name": _("Laba Tahun Ini"),
            "account": _("Laba Tahun Ini"),
            "has_value": True,
            "currency": first_item['currency'],
            "indent": 1.0,
            "parent_account": first_item['parent_account'],
            "year_start_date": first_item['year_start_date'],
            "year_end_date": first_item['year_end_date'],
            "account_type": "Equity",
            "is_group": 0,
            key: provisional_profit_loss.get(key, 0),
            "total": provisional_profit_loss.get(key, 0)
        }

        # Insert 'laba_tahun_ini' before the last item
        equity.insert(-2, laba_tahun_ini)

        # Calculate the sum of the 'key' value for all equity items except the last one
        total_sum = sum(item[key] for item in equity[:-2])


        # Update the last item's 'key' value with the new sum
        equity[-2][key] = total_sum

    return equity


def sum_aset_lancar(kas_setara_kas, piutang_usaha, persediaan, aset_lancar_lainnya, period_list, company, currency=None, consolidated=False):
    total = 0
    aset_lancar = {
        "account_name": _("Jumlah Aset Lancar"),
        "account": _("Jumlah Aset Lancar"),
        "warn_if_negative": True,
        "currency": currency or frappe.get_cached_value("Company", company, "default_currency"),
    }

    has_value = False

    for period in period_list:
        key = period if consolidated else period.key

        total_kas_setara_kas = sum_values(kas_setara_kas, key)
        total_piutang_usaha = sum_values(piutang_usaha, key)
        total_persediaan = sum_values(persediaan, key)
        total_aset_lancar_lainnya = sum_values(aset_lancar_lainnya, key)

        aset_lancar[key] = total_kas_setara_kas + total_piutang_usaha + \
            total_persediaan + total_aset_lancar_lainnya

        if aset_lancar[key]:
            has_value = True

        total += flt(aset_lancar[key])
        aset_lancar["total"] = total

    if has_value:
        return aset_lancar


def sum_aset_tidak_lancar(nilai_histori, akumulasi_penyusutan, period_list, company, currency=None, consolidated=False):
    total = 0
    aset_tidak_lancar = {
        "account_name": _("Jumlah Aset Tidak Lancar"),
        "account": _("Jumlah Aset Tidak Lancar"),
        "warn_if_negative": True,
        "currency": currency or frappe.get_cached_value("Company", company, "default_currency"),
    }

    has_value = False

    for period in period_list:
        key = period if consolidated else period.key

        total_nilai_histori = sum_values(nilai_histori, key)
        total_akumulasi_penyusutan = sum_values(akumulasi_penyusutan, key)

        aset_tidak_lancar[key] = total_nilai_histori + \
            total_akumulasi_penyusutan

        if aset_tidak_lancar[key]:
            has_value = True

        total += flt(aset_tidak_lancar[key])
        aset_tidak_lancar["total"] = total

    if has_value:
        return aset_tidak_lancar

def sum_all_asset(kas_setara_kas, piutang_usaha, persediaan, aset_lancar_lainnya, nilai_histori, akumulasi_penyusutan, period_list, company, currency=None, consolidated=False):
    total_aset_lancar = sum_aset_lancar(kas_setara_kas, piutang_usaha, persediaan, aset_lancar_lainnya, period_list, company, currency, consolidated)
    total_aset_tidak_lancar = sum_aset_tidak_lancar(nilai_histori, akumulasi_penyusutan, period_list, company, currency, consolidated)

    total = 0
    all_assets = {
        "account_name": _("Jumlah Aset"),
        "account": _("Jumlah Aset"),
        "warn_if_negative": True,
        "currency": currency or frappe.get_cached_value("Company", company, "default_currency"),
    }

    has_value = False

    for period in period_list:
        key = period if consolidated else period['key']

        total_lancar = total_aset_lancar.get(key, 0) if total_aset_lancar else 0
        total_tidak_lancar = total_aset_tidak_lancar.get(key, 0) if total_aset_tidak_lancar else 0

        all_assets[key] = total_lancar + total_tidak_lancar

        if all_assets[key]:
            has_value = True

        total += flt(all_assets[key])
        all_assets["total"] = total

    if has_value:
        return all_assets

def sum_kewajiban_jangka_pendek(utang_usaha, kewajiban_jangka_pendek_lainnya, period_list, company, currency=None, consolidated=False):
    total = 0
    kewajiban_jangka_pendek = {
        "account_name": _("Jumlah Kewajiban Jangka Pendek"),
        "account": _("Jumlah Kewajiban Jangka Pendek"),
        "warn_if_negative": True,
        "currency": currency or frappe.get_cached_value("Company", company, "default_currency"),
    }

    has_value = False

    for period in period_list:
        key = period if consolidated else period.key

        total_utang_usaha = sum_values(utang_usaha, key)
        total_kewajiban_jangka_pendek_lainnya = sum_values(
            kewajiban_jangka_pendek_lainnya, key)

        kewajiban_jangka_pendek[key] = total_utang_usaha + \
            total_kewajiban_jangka_pendek_lainnya

        if kewajiban_jangka_pendek[key]:
            has_value = True

        total += flt(kewajiban_jangka_pendek[key])
        kewajiban_jangka_pendek["total"] = total

    if has_value:
        return kewajiban_jangka_pendek


def sum_kewajiban(utang_usaha, kewajiban_jangka_pendek_lainnya, period_list, company, currency=None, consolidated=False):
    total = 0
    kewajiban = {
        "account_name": _("Jumlah Kewajiban"),
        "account": _("Jumlah Kewajiban"),
        "warn_if_negative": True,
        "currency": currency or frappe.get_cached_value("Company", company, "default_currency"),
    }

    has_value = False

    for period in period_list:
        key = period if consolidated else period.key

        total_utang_usaha = sum_values(utang_usaha, key)
        total_kewajiban_jangka_pendek_lainnya = sum_values(
            kewajiban_jangka_pendek_lainnya, key)

        kewajiban[key] = total_utang_usaha + \
            total_kewajiban_jangka_pendek_lainnya

        if kewajiban[key]:
            has_value = True

        total += flt(kewajiban[key])
        kewajiban["total"] = total

    if has_value:
        return kewajiban


def sum_liabilitas_dan_ekuitas(utang_usaha, kewajiban_jangka_pendek_lainnya, equity, 
                               period_list, company, currency=None, consolidated=False):
    total = 0
    liabilitas_dan_ekuitas = {
        "account_name": _("Jumlah Liabilitas dan Ekuitas"),
        "account": _("Jumlah Liabilitas dan Ekuitas"),
        "warn_if_negative": True,
        "currency": currency or frappe.get_cached_value("Company", company, "default_currency"),
    }

    has_value = False

    for period in period_list:
        key = period if consolidated else period.key

        total_utang_usaha = sum_values(utang_usaha, key)
        total_kewajiban_jangka_pendek_lainnya = sum_values(
            kewajiban_jangka_pendek_lainnya, key)
        total_equity = sum_values(equity, key)

        liabilitas_dan_ekuitas[key] = total_utang_usaha + \
            total_kewajiban_jangka_pendek_lainnya + total_equity

        if liabilitas_dan_ekuitas[key]:
            has_value = True

        total += flt(liabilitas_dan_ekuitas[key])
        liabilitas_dan_ekuitas["total"] = total

    if has_value:
        return liabilitas_dan_ekuitas


def get_provisional_profit_loss(
    kas_setara_kas, piutang_usaha, persediaan, aset_lancar_lainnya, nilai_histori, akumulasi_penyusutan, utang_usaha, kewajiban_jangka_pendek_lainnya, equity, period_list, company, currency=None, consolidated=False
):
    provisional_profit_loss = {}
    total_row = {}
    total = total_row_total = 0

    currency = currency or frappe.get_cached_value(
        "Company", company, "default_currency")
    total_row = {
        "account_name": "'" + _("Total (Credit)") + "'",
        "account": "'" + _("Total (Credit)") + "'",
        "warn_if_negative": True,
        "currency": currency,
    }

    has_value = False

    for period in period_list:
        key = period if consolidated else period.key
        effective_asset, effective_liability, = 0.0, 0.0

        effective_asset += sum_values(kas_setara_kas, key)
        effective_asset += sum_values(piutang_usaha, key)
        effective_asset += sum_values(persediaan, key)
        effective_asset += sum_values(aset_lancar_lainnya, key)
        effective_asset += sum_values(nilai_histori, key)
        effective_asset += sum_values(akumulasi_penyusutan, key)

        effective_liability += sum_values(utang_usaha, key)
        effective_liability += sum_values(kewajiban_jangka_pendek_lainnya, key)
        effective_liability += sum_values(equity, key)

        provisional_profit_loss[key] = flt(
            effective_asset) - flt(effective_liability)
        total_row[key] = effective_liability + provisional_profit_loss[key]

        if provisional_profit_loss[key]:
            has_value = True

        total += flt(provisional_profit_loss[key])
        provisional_profit_loss["total"] = total

        total_row_total += flt(total_row[key])
        total_row["total"] = total_row_total

    if has_value:
        provisional_profit_loss.update(
            {
                "account_name": "'" + _("Provisional Profit / Loss (Credit)") + "'",
                "account": "'" + _("Provisional Profit / Loss (Credit)") + "'",
                "warn_if_negative": True,
                "currency": currency,
            }
        )

    return provisional_profit_loss, total_row


def check_opening_balance(
    kas_setara_kas, piutang_usaha, persediaan, aset_lancar_lainnya, nilai_histori, akumulasi_penyusutan, utang_usaha, kewajiban_jangka_pendek_lainnya, equity,
):
    # Check if previous year balance sheet closed
    opening_balance = 0
    float_precision = cint(frappe.db.get_default("float_precision")) or 2
    if kas_setara_kas:
        opening_balance = flt(
            kas_setara_kas[-1].get("opening_balance", 0), float_precision)
    if piutang_usaha:
        opening_balance += flt(
            piutang_usaha[-1].get("opening_balance", 0), float_precision)
    if persediaan:
        opening_balance += flt(
            persediaan[-1].get("opening_balance", 0), float_precision)
    if aset_lancar_lainnya:
        opening_balance += flt(
            aset_lancar_lainnya[-1].get("opening_balance", 0), float_precision)
    if nilai_histori:
        opening_balance += flt(
            nilai_histori[-1].get("opening_balance", 0), float_precision)
    if akumulasi_penyusutan:
        opening_balance -= flt(
            akumulasi_penyusutan[-1].get("opening_balance", 0), float_precision)
    if utang_usaha:
        opening_balance -= flt(
            utang_usaha[-1].get("opening_balance", 0), float_precision)
    if kewajiban_jangka_pendek_lainnya:
        opening_balance -= flt(
            kewajiban_jangka_pendek_lainnya[-1].get("opening_balance", 0), float_precision)
    if equity:
        opening_balance -= flt(equity[-1].get("opening_balance",
                               0), float_precision)

    opening_balance = flt(opening_balance, float_precision)
    if opening_balance:
        return _("Previous Financial Year is not closed"), opening_balance
    return None, None


def get_report_summary(
        period_list,
        kas_setara_kas,
        piutang_usaha,
        persediaan,
        aset_lancar_lainnya,
        nilai_histori,
        akumulasi_penyusutan,
        utang_usaha,
        kewajiban_jangka_pendek_lainnya,
        equity,
        provisional_profit_loss,
        currency,
        filters,
        consolidated=False,
):

    net_asset, net_liability, net_equity, net_provisional_profit_loss = 0.0, 0.0, 0.0, 0.0

    if filters.get("accumulated_values"):
        period_list = [period_list[-1]]

    # from consolidated financial statement
    if filters.get("accumulated_in_group_company"):
        period_list = get_filtered_list_for_consolidated_report(
            filters, period_list)

    for period in period_list:
        key = period if consolidated else period.key

        net_asset += sum_values(kas_setara_kas, key)
        net_asset += sum_values(piutang_usaha, key)
        net_asset += sum_values(persediaan, key)
        net_asset += sum_values(aset_lancar_lainnya, key)
        net_asset += sum_values(nilai_histori, key)
        net_asset += sum_values(akumulasi_penyusutan, key)
        net_liability += sum_values(utang_usaha, key)
        net_liability += sum_values(kewajiban_jangka_pendek_lainnya, key)
        net_equity += sum_values(equity, key)
        net_provisional_profit_loss += provisional_profit_loss.get(key)

    return [
        {"value": net_asset, "label": _(
            "Total Asset"), "datatype": "Currency", "currency": currency},
        {
            "value": net_liability,
            "label": _("Total Liability"),
            "datatype": "Currency",
            "currency": currency,
        },
        {"value": net_equity, "label": _(
            "Total Equity"), "datatype": "Currency", "currency": currency},
        {
            "value": net_provisional_profit_loss,
            "label": _("Provisional Profit / Loss (Credit)"),
            "indicator": "Green" if net_provisional_profit_loss > 0 else "Red",
            "datatype": "Currency",
            "currency": currency,
        },
    ]


def get_chart_data(filters, columns, kas_setara_kas, piutang_usaha, persediaan, aset_lancar_lainnya, nilai_histori, akumulasi_penyusutan, utang_usaha, kewajiban_jangka_pendek_lainnya, equity,
                   ):
    labels = [d.get("label") for d in columns[2:]]

    asset_data, liability_data, equity_data = [], [], []
    total_asset, total_liability, total_equity = 0.0, 0.0, 0.0

    for p in columns[2:]:
        if kas_setara_kas:
            total_asset += sum_values(kas_setara_kas, p.get("fieldname"))
        if piutang_usaha:
            total_asset += sum_values(piutang_usaha, p.get("fieldname"))
        if persediaan:
            total_asset += sum_values(persediaan, p.get("fieldname"))
        if aset_lancar_lainnya:
            total_asset += sum_values(aset_lancar_lainnya, p.get("fieldname"))
        if nilai_histori:
            total_asset += sum_values(nilai_histori, p.get("fieldname"))
        if akumulasi_penyusutan:
            total_asset += sum_values(akumulasi_penyusutan, p.get("fieldname"))
        if utang_usaha:
            total_liability += sum_values(utang_usaha, p.get("fieldname"))
        if kewajiban_jangka_pendek_lainnya:
            total_liability += sum_values(
                kewajiban_jangka_pendek_lainnya, p.get("fieldname"))
        if equity:
            total_equity += sum_values(equity, p.get("fieldname"))

    asset_data.append(total_asset)
    liability_data.append(total_liability)
    equity_data.append(total_equity)

    datasets = []
    if asset_data:
        datasets.append({"name": _("Assets"), "values": asset_data})
    if liability_data:
        datasets.append({"name": _("Liabilities"), "values": liability_data})
    if equity_data:
        datasets.append({"name": _("Equity"), "values": equity_data})

    chart = {"data": {"labels": labels, "datasets": datasets}}

    if not filters.accumulated_values:
        chart["type"] = "bar"
    else:
        chart["type"] = "line"

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