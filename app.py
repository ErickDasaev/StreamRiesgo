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

conInfo = outData[outData['company_id'] == optionid].iloc[0]