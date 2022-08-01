import streamlit as st
import pandas as pd
import numpy as np
from calcs import *

st.title('Medidas de Riesgo Fiscal')

invoices = pd.read_csv('data/datainvoices.csv')
direct_debit = pd.read_csv('data/dataddebit.csv')
contracts_data = pd.read_csv('data/datacontracts.csv')
companies_all = pd.read_csv('data/datacompanies.csv')
outData = pd.read_csv('data/contractsSummary.csv')

st.write('Empresas:')

option = st.sidebar.selectbox('Companies', tuple(set(companies_all['business_name'].unique())))
optionid = companies_all[companies_all['business_name'] == option].iloc[0]['id']
st.write('Contratos:')
st.dataframe(data=contracts_data[contracts_data['company_id'] == optionid], width=None, height=None)

st.write('Facturas:')
st.dataframe(data=invoices[invoices['company_id'] == optionid], width=None, height=None)


if len(outData[outData['company_id'] == optionid]) > 0:

    conInfo = outData[outData['company_id'] == optionid].iloc[0]

    for index, value in conInfo.loc[['sat_declaration_rate',
               'total_sat_rate',
                'avr_cf_l3m',
                'avr_cf_l6m',
                'avr_cf_l12m',
                'avr_gross_m_l3m',
                'avr_gross_m_l6m',
                'avr_gross_m_l12m',
                'avr_net_m_l3m',
                'avr_net_m_l6m',
                'avr_net_m_l12m',
                'av_itmes_l3m',
                'av_itmes_l6m',
                'av_itmes_l12m',
                'av_amount_l3m',
                'av_amount_l6m',
                'av_amount_l12m',
                'moratory_av_itmes_l3m',
               'moratory_av_itmes_l6m',
               'moratory_av_itmes_l12m',
               'moratory_av_amount_l3m',
               'moratory_av_amount_l6m',
               'moratory_av_amount_l12m',
                'meli_fin_var',
                'peg_invoicing',
                'concentration_clients',
                'data_sat_days',
                'l3m_total_employees',
            'l6m_total_employees',
            'l12m_total_employees']].items():
        st.markdown(index)
        st.subheader(value)

else:
    st.header('No contract was found for this customer')