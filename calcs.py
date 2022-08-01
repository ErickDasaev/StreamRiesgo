import pandas as pd
from pydantic import BaseSettings, Field, PostgresDsn
import pendulum
import datetime

def get_incomes_by_company_info(invoices, company_id, date):
    incomes = invoices[
        (invoices.certified_at <= date) & (invoices.company_id == company_id) & (invoices.type == 'I') & (
                    invoices.is_issuer == True)]

    if incomes.empty:
        return False, False, False, False
    product_sales = (
        incomes[['tipo', 'descr_familia', 'product_identification', 'descr_articulo', 'unit_amount']]
            .groupby(by=['tipo', 'descr_familia', 'product_identification', 'descr_articulo']).sum().reset_index()
    )

    quantile_5 = product_sales[product_sales.tipo == 'producto'].sort_values(by='unit_amount',
                                                                             ascending=False).quantile(.05)
    # quantile_5 = 0
    sales_products_list = (
        product_sales
        [(product_sales.tipo == 'producto')
         & (product_sales.unit_amount >= float(quantile_5))]
            .sort_values(by='unit_amount', ascending=False)

    )['product_identification'].unique()

    month_sales_by_item = (
        incomes[['certified_at', 'descr_familia', 'tax_amount', 'total_amount']][
            incomes.product_identification.isin(sales_products_list)]
            .groupby(by=[pd.Grouper(key='certified_at', freq="M"), 'descr_familia']).sum().reset_index()
    )

    month_sales_by_item['servicio_producto'] = 'producto'

    month_sales_by_service = (
        incomes[['certified_at', 'descr_familia', 'tax_amount', 'total_amount']][incomes.tipo == 'servicio']
            .groupby(by=[pd.Grouper(key='certified_at', freq="M"), 'descr_familia']).sum().reset_index()

    )
    month_sales_by_service['servicio_producto'] = 'servicio'

    month_sales_total_by_type = pd.concat([month_sales_by_item, month_sales_by_service])

    month_sales_total_by_type['total'] = month_sales_total_by_type['tax_amount'] + month_sales_total_by_type[
        'total_amount']

    df_graph = month_sales_total_by_type[['certified_at', 'servicio_producto', 'total']].groupby(
        by=[pd.Grouper(key='certified_at', freq="M"), 'servicio_producto']).sum().reset_index()

    total_sales = month_sales_total_by_type[['certified_at', 'total']].groupby(by='certified_at').sum().reset_index()

    total_sales['servicio_producto'] = 'total_venta'

    outcomes_desition = df_graph.groupby(by='servicio_producto').sum().reset_index()
    outcomes_desition['percentage'] = outcomes_desition['total'] / outcomes_desition['total'].sum()
    outcomes_desition = outcomes_desition.sort_values(by='percentage', ascending=False)

    if outcomes_desition.empty:
        return False, False, False, False
    outcomes_desition_str = "producto"

    month_sales = pd.concat([df_graph, total_sales])
    return total_sales, df_graph, outcomes_desition_str, month_sales


def get_gmv_df_by_client(company_id, date, gmv_df):
    gmv_df['date'] = pd.to_datetime(gmv_df['date']).dt.date
    client_gmv = gmv_df[(gmv_df.date <= date) & (gmv_df.client_id == company_id)]

    return client_gmv


def get_sat_rates(month_sales, gmv_df):
    def get_sat_rate(row):
        gmv = row['gmv']

        if gmv == 0:
            return 0, 0, 0

        gmv_date = row['date']

        gmv_df_date = month_sales[(month_sales.servicio_producto == 'total_venta') & (month_sales.date == gmv_date)]

        if gmv_df_date.empty:
            return 0, 0, 0

        sat_gmv = gmv_df_date['total'].iloc[0]

        if sat_gmv == 0:
            return 0, 0, 0

        return sat_gmv, gmv / sat_gmv, sat_gmv / gmv

    month_sales['date'] = month_sales['certified_at']
    month_sales['date'] = pd.to_datetime(month_sales['date']).dt.date

    gmv_df['date'] = pd.to_datetime(gmv_df['date'])

    monthly_gmv_df = gmv_df[['date', 'gmv']].groupby(by=pd.Grouper(key='date', freq="M")).sum().reset_index()

    monthly_gmv_df['servicio_producto'] = 'conn'
    monthly_gmv_df['total'] = monthly_gmv_df['gmv']
    monthly_gmv_df['date'] = pd.to_datetime(monthly_gmv_df['date']).dt.date

    monthly_gmv_df[['sat_gmv', 'sat_vs_conn', 'conn_vs_sat']] = monthly_gmv_df.apply(get_sat_rate, axis=1,
                                                                                     result_type='expand')

    total_gmv_comp = len(monthly_gmv_df[monthly_gmv_df.total > 0])
    total_sales_grater_sat = len(monthly_gmv_df[(monthly_gmv_df.total > 0) & (monthly_gmv_df.sat_vs_conn > 1)])
    sat_declaration_rate = total_sales_grater_sat / (total_gmv_comp - 1)

    compare_total_df = monthly_gmv_df[(monthly_gmv_df.total > 0) & (monthly_gmv_df.sat_gmv > 0)]

    total_sat_rate = compare_total_df['sat_gmv'].sum() / compare_total_df['total'].sum()

    print(compare_total_df['sat_gmv'].sum(), compare_total_df['total'].sum())

    return sat_declaration_rate, total_sat_rate


def get_company_expenses(invoices, company_id, date, one_y_date_datetime, outcomes_desition_str):
    print("-------------------------oper outcome")
    expenses_df = invoices[
        (invoices.certified_at <= date) & (invoices.company_id == company_id) & (invoices.is_issuer == False) & (
                    invoices.tipo == outcomes_desition_str)][
        ['certified_at', 'tax_amount', 'total_amount', 'descr_articulo', 'descr_familia']]
    # expenses_df = invoices[(invoices.is_issuer ==  False)&(invoices.tipo=='servicio')][['certified_at', 'tax_amount', 'total_amount', 'descr_articulo', 'descr_familia']]

    expenses_df['total'] = expenses_df['tax_amount'] + expenses_df['total_amount']
    monthly_expenses = expenses_df[['certified_at', 'total']].groupby(
        by=[pd.Grouper(key='certified_at', freq="M")]).sum().reset_index()
    monthly_expenses['servicio_producto'] = 'operativos'

    products_excluded_list = '|'.join(['Publicidad', 'publicitarias', 'publicidad', 'Publicitarias'])
    print("-------------------------mkt outcome")
    mkt_expenses_df = (
        invoices[(invoices.certified_at <= date) & (invoices.company_id == company_id) &
                 (invoices.is_issuer == False) &
                 (invoices['product_identification'].str.startswith('821')) &
                 (invoices['descr_articulo'].str.contains(products_excluded_list))

                 ]
        [['certified_at', 'descr_familia', 'descr_articulo', 'tax_amount', 'total_amount']]
    )

    mkt_exp_by_pruduct = mkt_expenses_df.groupby(
        by=[pd.Grouper(key='certified_at', freq="M"), 'descr_familia', 'descr_articulo']).sum().reset_index()

    mkt_expenses_df['total'] = mkt_expenses_df['tax_amount'] + mkt_expenses_df['total_amount']

    month_mkt_expenses = mkt_expenses_df[['certified_at', 'total']].groupby(
        by=pd.Grouper(key='certified_at', freq="M")).sum().reset_index()
    month_mkt_expenses['servicio_producto'] = 'MKT'

    print("-------------------------payroll outcome")
    pr_df = invoices[(invoices.certified_at <= date) & (invoices.company_id == company_id) & (invoices.type == 'N') & (
                invoices.is_issuer == True)][
        ['id', 'certified_at', 'rfc_receiver', 'subtotal', 'total']].drop_duplicates()

    pr_month_info = pr_df.groupby(by=[pd.Grouper(key='certified_at', freq="M")]).agg(
        {'rfc_receiver': ['nunique'], 'total': ['mean', 'sum'], 'subtotal': ['mean', 'sum']}).reset_index()

    pr_month_info.columns = ['_'.join(col).strip() for col in pr_month_info.columns.values]
    # pr_month_info['certified_at_'] = pr_month_info['certified_at_'].dt.date
    employees_df = pr_month_info
    l3m_total_employees = employees_df['rfc_receiver_nunique'][-4:-1].mean()
    l6m_total_employees = employees_df['rfc_receiver_nunique'][-7:-1].mean()
    l12m_total_employees = employees_df['rfc_receiver_nunique'][-13:-1].mean()

    pr_month_expenses = pr_month_info[['certified_at_', 'subtotal_sum']].rename(
        columns={'certified_at_': 'certified_at', 'subtotal_sum': 'total'})

    pr_month_expenses['servicio_producto'] = 'pay_roll'

    total_expenses = pd.concat([monthly_expenses, month_mkt_expenses, pr_month_expenses])

    return total_expenses, monthly_expenses, month_mkt_expenses, pr_month_expenses, l3m_total_employees, l6m_total_employees, l12m_total_employees


def get_cashflow_burn(total_expenses, total_sales):
    # display(total_expenses)
    # Gross cashflows
    cogs_df = total_expenses[total_expenses.servicio_producto == 'operativos']
    cogs_df['total'] = cogs_df['total'] * -1
    monthly_gross_cf = pd.concat([cogs_df, total_sales])
    monthly_gross_cf = monthly_gross_cf.groupby(by='certified_at').sum().reset_index()
    monthly_gross_cf = monthly_gross_cf = monthly_gross_cf.rename(columns={"total": "gross_cf"})
    monthly_gross_cf = pd.merge(monthly_gross_cf, total_sales, on='certified_at', how='left')
    monthly_gross_cf['gross_margin'] = monthly_gross_cf['gross_cf'] / monthly_gross_cf['total']

    avr_gross_m_l3m = monthly_gross_cf['gross_margin'][-4:-1].mean()
    avr_gross_m_l6m = monthly_gross_cf['gross_margin'][-6:-1].mean()
    avr_gross_m_l12m = monthly_gross_cf['gross_margin'][-13:-1].mean()

    # Net cashflows
    monthly_total_expenses = total_expenses.groupby(by=pd.Grouper(key='certified_at', freq="M")).sum().reset_index()

    monthly_total_expenses['servicio_producto'] = 'total_gastos'
    monthly_total_expenses['total'] = monthly_total_expenses['total'] * -1
    monthly_net_cf = pd.concat([monthly_total_expenses, total_sales])
    monthly_net_cf = monthly_net_cf.groupby(by='certified_at').sum().reset_index()

    monthly_net_cf = monthly_net_cf.rename(columns={"total": "net_cf"})
    monthly_net_cf = pd.merge(monthly_net_cf, total_sales, on='certified_at', how='left')
    monthly_net_cf['net_margin'] = monthly_net_cf['net_cf'] / monthly_net_cf['total']
    avr_net_m_l3m = monthly_net_cf['net_margin'][-4:-1].mean()
    avr_net_m_l6m = monthly_net_cf['net_margin'][-6:-1].mean()
    avr_net_m_l12m = monthly_net_cf['net_margin'][-13:-1].mean()

    avr_cf_l3m = monthly_net_cf['net_cf'][-4:-1].mean()
    avr_cf_l6m = monthly_net_cf['net_cf'][-7:-1].mean()
    avr_cf_l12m = monthly_net_cf['net_cf'][-13:-1].mean()

    return (
        avr_cf_l3m,
        avr_cf_l6m,
        avr_cf_l12m,
        avr_gross_m_l3m,
        avr_gross_m_l6m,
        avr_gross_m_l12m,
        avr_net_m_l3m,
        avr_net_m_l6m,
        avr_net_m_l12m

    )


def get_invoices_by_client(company_id, date, invoices_base):
    df_invoives_filtered = invoices_base[(invoices_base.company_id == company_id) & (invoices_base.certified_at <= date)]

    return invoices_base[(invoices_base.company_id == company_id) & (invoices_base.certified_at <= date)]

def meli_fin(invoices):
    meli_df = invoices[invoices.rfc_issuer=='MLE1702168U1']
    if len(meli_df) == 0:
        return 0
    else:
        return 1


def get_moratory_info(invoices, date, one_y_date_datetime):
    df_fin_issuers = (invoices
    [(invoices.is_issuer == False) &
     (invoices.certified_at <= date) & (invoices.certified_at >= one_y_date_datetime) &
     (invoices['product_identification'].str.startswith('841')) & (
                 invoices.descr_articulo != 'Servicios de facturación')]
    [['id', 'certified_at',
      'rfc_issuer', 'name_issuer',
      'product_identification',
      'descr_articulo',
      'description',
      'currency',
      'subtotal',
      'total']])

    # print(df_fin_issuers.certified_at.max())
    df_fin_issuers['item_total'] = df_fin_issuers['subtotal'] + df_fin_issuers['total']
    fin_invoiced = df_fin_issuers[['certified_at', 'item_total']].groupby(
        by=pd.Grouper(key='certified_at', freq="M")).agg({'item_total': ['sum', 'count']})
    fin_invoiced.columns = ['_'.join(col).strip() for col in fin_invoiced.columns.values]

    av_itmes_l3m = fin_invoiced['item_total_count'][-4:-1].mean()
    av_itmes_l6m = fin_invoiced['item_total_count'][-7:-1].mean()
    av_itmes_l12m = fin_invoiced['item_total_count'][-13:-1].mean()

    av_amount_l3m = fin_invoiced['item_total_sum'][-4:-1].mean()
    av_amount_l6m = fin_invoiced['item_total_sum'][-7:-1].mean()
    av_amount_l12m = fin_invoiced['item_total_sum'][-13:-1].mean()

    df_fin_issuers['description'] = df_fin_issuers['description'].fillna("NA")

    searchfor = ['Morat', 'MORAT', 'morat']

    moratory_df = df_fin_issuers[df_fin_issuers.description.str.contains('|'.join(searchfor))].sort_values(
        by=['rfc_issuer', 'certified_at'])
    moratory_invoiced = moratory_df[['certified_at', 'item_total']].groupby(
        by=pd.Grouper(key='certified_at', freq="M")).agg({'item_total': ['sum', 'count']})
    moratory_invoiced.columns = ['_'.join(col).strip() for col in moratory_invoiced.columns.values]

    moratory_av_itmes_l3m = moratory_invoiced['item_total_count'][-4:-1].mean()
    moratory_av_itmes_l6m = moratory_invoiced['item_total_count'][-7:-1].mean()
    moratory_av_itmes_l12m = moratory_invoiced['item_total_count'][-13:-1].mean()

    moratory_av_amount_l3m = moratory_invoiced['item_total_sum'][-4:-1].mean()
    moratory_av_amount_l6m = moratory_invoiced['item_total_sum'][-7:-1].mean()
    moratory_av_amount_l12m = moratory_invoiced['item_total_sum'][-13:-1].mean()

    return (av_itmes_l3m,
            av_itmes_l6m,
            av_itmes_l12m,
            av_amount_l3m,
            av_amount_l6m,
            av_amount_l12m,
            moratory_av_itmes_l3m,
            moratory_av_itmes_l6m,
            moratory_av_itmes_l12m,
            moratory_av_amount_l3m,
            moratory_av_amount_l6m,
            moratory_av_amount_l12m
            )


def get_client_concentration_info(invoices, date):
    clients_df = (
        invoices[['certified_at', 'rfc_receiver', 'name_receiver', 'tax', 'subtotal', 'total']]
        [(invoices.type == 'I') & (invoices.certified_at <= date) & (invoices.is_issuer == True)])
    filter_date = pendulum.parse(str(clients_df['certified_at'].max().date())).date().subtract(months=13)
    filter_date = pendulum.datetime(filter_date.year, filter_date.month, filter_date.day)
    clients_conglomerate = clients_df[clients_df.certified_at >= filter_date][
        ['rfc_receiver', 'name_receiver', 'tax', 'subtotal', 'total']].groupby(
        by=['rfc_receiver', 'name_receiver']).sum().reset_index()
    clients_conglomerate['percentage'] = clients_conglomerate['total'] / clients_conglomerate['total'].sum()
    history_df = clients_conglomerate.sort_values(by='percentage', ascending=False)
    peg_invoicing = history_df[history_df.rfc_receiver == 'XAXX010101000']['percentage'].sum()
    concentration_clients = history_df[history_df.rfc_receiver != 'XAXX010101000'][0:5]['percentage'].sum()

    return peg_invoicing, concentration_clients


def get_all_analisis(row, invoices_base, gmv_df):
    company_id = row['company_id']
    date = row['starts_on']

    date_pendulum = pendulum.parse(str(date)).date()
    date_datetime = pendulum.datetime(date.year, date.month, date.day)
    one_y_date_datetime = pendulum.datetime(date.year - 1, date.month, date.day)

    invoices_df = get_invoices_by_client(company_id, date_datetime,invoices_base)
    print(company_id)
    print(date_datetime)
    if invoices_df.empty:
        return (0, 0,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0

                )

    invoices_min_date = pendulum.parse(str(invoices_df.certified_at.min())).date()

    date_s = date_pendulum - invoices_min_date
    print(company_id, date, invoices_min_date, date_s.days)

    data_sat_days = date_s.days

    print(data_sat_days)
    if invoices_df.empty or data_sat_days < 200:
        return (0, 0,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0

                )

    print("-----------stage incomes")
    total_sales, df_graph, outcomes_desition_str, month_sales = get_incomes_by_company_info(invoices_df, company_id,
                                                                                            date_datetime)
    if total_sales is False:
        return (0, 0,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0
                )

    print("-----------stage gmv")
    client_gmv = get_gmv_df_by_client(company_id, date,gmv_df)
    print("-----------sat declaration rate")
    sat_declaration_rate, total_sat_rate = get_sat_rates(month_sales, client_gmv)

    print("-----------stage sat expenses")
    (total_expenses,
     monthly_expenses,
     month_mkt_expenses,
     pr_month_expenses,
     l3m_total_employees,
     l6m_total_employees,
     l12m_total_employees) = get_company_expenses(invoices_df, company_id, date_datetime, one_y_date_datetime,
                                                  outcomes_desition_str)
    print("-----------stage burn rate")
    (
        avr_cf_l3m,
        avr_cf_l6m,
        avr_cf_l12m,
        avr_gross_m_l3m,
        avr_gross_m_l6m,
        avr_gross_m_l12m,
        avr_net_m_l3m,
        avr_net_m_l6m,
        avr_net_m_l12m

    ) = get_cashflow_burn(total_expenses, total_sales)

    print("-----------stage fin issuers")

    meli_fin_var = meli_fin(invoices_df)

    (av_itmes_l3m,
     av_itmes_l6m,
     av_itmes_l12m,
     av_amount_l3m,
     av_amount_l6m,
     av_amount_l12m,
     moratory_av_itmes_l3m,
     moratory_av_itmes_l6m,
     moratory_av_itmes_l12m,
     moratory_av_amount_l3m,
     moratory_av_amount_l6m,
     moratory_av_amount_l12m) = get_moratory_info(invoices_df, date_datetime, one_y_date_datetime)
    print("-----------stage clients")

    peg_invoicing, concentration_clients = get_client_concentration_info(invoices_df, date_datetime)

    return (sat_declaration_rate,
            total_sat_rate,
            avr_cf_l3m,
            avr_cf_l6m,
            avr_cf_l12m,
            avr_gross_m_l3m,
            avr_gross_m_l6m,
            avr_gross_m_l12m,
            avr_net_m_l3m,
            avr_net_m_l6m,
            avr_net_m_l12m,
            av_itmes_l3m,
            av_itmes_l6m,
            av_itmes_l12m,
            av_amount_l3m,
            av_amount_l6m,
            av_amount_l12m,
            moratory_av_itmes_l3m,
            moratory_av_itmes_l6m,
            moratory_av_itmes_l12m,
            moratory_av_amount_l3m,
            moratory_av_amount_l6m,
            moratory_av_amount_l12m,
            meli_fin_var,
            peg_invoicing,
            concentration_clients,
            data_sat_days,
            l3m_total_employees,
            l6m_total_employees,
            l12m_total_employees

            )

