import streamlit as st
import pandas as pd
import numpy as np
from calcs import *

st.title('Medidas de Riesgo Fiscal')

invoices = pd.read_csv('data/invoices.csv')
direct_debit = pd.read_csv('data/ddebit.csv')
contracts_data = pd.read_csv('data/contracts.csv')
companies_all = pd.read_csv('data/companies.csv')

st.write('Empresas:')

option = st.sidebar.selectbox('Companies', tuple(set(companies_all['business_name'].unique())))
optionid = companies_all[companies_all['business_name']==option].iloc[0]['id']
st.write('Contratos:')
st.dataframe(data=contracts_data , width=None, height=None)