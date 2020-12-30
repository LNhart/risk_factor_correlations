from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import pandas as pd
import os
import pickle
import numpy as np

def train_model(df):
    corpus = df.values.flatten()
    notna_corpus = corpus[~pd.isnull(corpus)]
    vectorizer = TfidfVectorizer(stop_words="english", min_df=2)
    vectorizer = vectorizer.fit(notna_corpus)

    return vectorizer

def get_reports_for_date(df, date):

    df_date = df.loc[date]
    df_date = df_date.dropna()

    return df_date

def compute_cosine_similarity_matrix(reports):

    vector = vectorizer.transform(reports)

    matrix = cosine_similarity(vector)

    df = pd.DataFrame(matrix, index=reports.index, columns=reports.index)

    return df

def get_returns_for_period(df, start, stop):

    df = df.loc[start:stop]
    #print(df)
    df = df.dropna(axis=1)

    return df


def compute_cov_matrix(returns):

    matrix = np.corrcoef(returns.values.transpose())

    df = pd.DataFrame(matrix, index=returns.columns, columns=returns.columns)

    return df

def returns_reports_in_both(returns, reports):

    returns_companies = returns.columns
    reports_companies = reports.columns

    in_both = returns_companies.intersection(reports_companies)

    #print(in_both)

    return returns.loc[in_both, in_both], reports.loc[in_both, in_both]




df = pd.read_csv("data/reports.csv", dtype="string", index_col="date")
df.index = pd.to_datetime(df.index)

if os.path.isfile("vectorizer.p"):
    vectorizer = pickle.load(open("vectorizer.p", "rb"))
else:
    vectorizer = train_model(df)
    pickle.dump(vectorizer, open("vectorizer.p", "wb"))

reports = get_reports_for_date(df, "31-12-2006")

similarities = compute_cosine_similarity_matrix(reports)

returns = pd.read_csv("data/stock_returns.csv", index_col="Date")
returns.index = pd.to_datetime(returns.index)

returns_period = get_returns_for_period(returns, "01-01-2007", "31-03-2007")

cov = compute_cov_matrix(returns_period)

cov, similarities = returns_reports_in_both(cov, similarities)

cov = cov.values.flatten()
similarities = similarities.values.flatten()

print(np.corrcoef(cov, similarities))
#print(returns_reports_in_both(cov, similarities)[0].shape)
#print(returns_reports_in_both(cov, similarities)[1].shape)
