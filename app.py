import streamlit as st
import pandas as pd
import numpy as np

st.title('Medidas de Riesgo Fiscal')

invoices = pd.read_csv('data/invoices.csv')
direct_debit = pd.read_csv('data/ddebit.csv')
contracts_data = pd.read_csv('data/contracts.csv')
companies_all = pd.read_csv('data/companies.csv')

option = st.selectbox('Companies', tuple(set(companies_all['registered_name'].unique())))

st.write('Contratos:')
st.dataframe(data=contracts_data, width=None, height=None)