from sklearn.feature_extraction.text import TfidfVectorizer, CountVectorizer
from sklearn.decomposition import LatentDirichletAllocation
from sklearn.metrics.pairwise import cosine_similarity, pairwise_distances
from sklearn.linear_model import LinearRegression, ElasticNetCV, RidgeCV
from sklearn.covariance import LedoitWolf
from sklearn.preprocessing import StandardScaler
import pandas as pd
import os
import pickle
import numpy as np
from datetime import datetime
from sklearn.metrics import mean_squared_error, r2_score
from scipy.optimize import minimize
import matplotlib.pyplot as plt

def train_tfidf_model(df, train_last, idf=True):
    corpus = df.loc[:train_last].values.flatten()
    notna_corpus = corpus[~pd.isnull(corpus)]
    vectorizer = TfidfVectorizer(stop_words="english", strip_accents="unicode", min_df=10, use_idf=idf)
    vectorizer = vectorizer.fit(notna_corpus)

    return vectorizer

def train_lda_model(df, train_last):
    corpus = df.loc[:train_last].values.flatten()
    notna_corpus = corpus[~pd.isnull(corpus)]
    vectorizer = CountVectorizer(stop_words="english", min_df=10)
    bow_vector = vectorizer.fit_transform(notna_corpus)

    print("training lda model")
    lda = LatentDirichletAllocation(n_components=25, random_state=0)

    lda.fit(bow_vector)

    print("finished training lda model")

    return vectorizer, lda

def get_reports_for_date(df, date):

    df_date = df.loc[date:date]
    df_date = df_date.dropna(axis=1)

    return df_date

def lda_features(reports, vectorizer, lda):

    if isinstance(reports, pd.DataFrame):
        reports = reports.iloc[0]

    vector_bow = vectorizer.transform(reports)

    vector_lda = lda.transform(vector_bow)

    return vector_lda

def tfidf_features(reports, vectorizer):

    if isinstance(reports, pd.DataFrame):
        reports = reports.iloc[0]

    #reports_np = reports.values.flatten()

    return vectorizer.transform(reports)


def get_returns_for_period(df, start, stop):

    df = df.loc[start:stop]
    #print(df)
    df = df.dropna(axis=1)

    return df


def compute_cov_matrix(returns):

    matrix = np.cov(returns.values.transpose())
    #matrix = np.corrcoef(returns.values.transpose())

    df = pd.DataFrame(matrix, index=returns.columns, columns=returns.columns)

    return df

def find_column_intersection(list_dfs):

    list_columns = []

    for df in list_dfs:
        #print(df.columns)
        list_columns.append(set(df.columns))

    in_all = set.intersection(*list_columns)

    list_dfs_new = []

    #print(in_all)

    for df in list_dfs:
        list_dfs_new.append(df[in_all])

    return list_dfs_new


def predict_cov_sample(prev_sample):

    return compute_cov_matrix(prev_sample).values


def predict_cov_cos_similarity(prev_sample, prev_similarities, similarities):

    prev_sample = prev_sample.values
    prev_sample_wout_diag = prev_sample[~np.eye(prev_sample.shape[0], dtype=bool)].reshape(prev_sample.shape[0], -1)

    similarities = similarities.values
    similarities_wout_diag = similarities[~np.eye(similarities.shape[0], dtype=bool)].reshape(similarities.shape[0], -1)

    prev_similarities = prev_similarities.values
    prev_similarities_wout_diag = prev_similarities[~np.eye(prev_similarities.shape[0], dtype=bool)].reshape(prev_similarities.shape[0], -1)


    shape = similarities.shape
    prev_similarities_wout_diag = prev_similarities_wout_diag.flatten().reshape(-1,1)
    prev_sample_wout_diag = prev_sample_wout_diag.flatten().reshape(-1,1)
    similarities = similarities.flatten().reshape(-1,1)
    mean_sim = np.mean(prev_similarities_wout_diag)
    sim_prev_demeaned = prev_similarities_wout_diag - mean_sim
    similarities_demeaned = similarities - mean_sim

    lr = LinearRegression()
    lr.fit(sim_prev_demeaned, prev_sample_wout_diag)

    pred = lr.predict(similarities_demeaned)

    pred = pred.reshape(shape)

    diag_prev = prev_sample.diagonal()

    pred[np.diag_indices_from(pred)] = diag_prev

    print(lr.intercept_)
    print(lr.coef_)

    return pred

def predict_mean(prev_sample):

    cov_mat = prev_sample.values
    without_diag = cov_mat[~np.eye(cov_mat.shape[0], dtype=bool)].reshape(cov_mat.shape[0], -1)
    mean_cov = np.mean(without_diag)
    mean_cov = np.full(cov_mat.shape, mean_cov)
    mean_variance = np.mean(np.diagonal(cov_mat))
    np.fill_diagonal(mean_cov, mean_variance)

    return mean_cov

def eval_predictions(true, pred):
    return (np.square(true - pred)).mean(axis=None)

def calculate_portfolio_var(w, sigma):

    w = np.asmatrix(w)
    sigma = np.asmatrix(sigma)

    #print((w.T * sigma) * w)

    return(w.transpose()*sigma*w)


def optimal_portfolio_weights(sigma):

    size = sigma.shape[0]
    sigma = np.asmatrix(sigma)
    #cons = ({'type': 'eq', 'fun': lambda x:  np.sum(x)-1.0})
    #start_weights = np.full((size, 1), 1 / size)

    one = np.ones((size, 1))
    one = np.asmatrix(one)

    w_star = (np.linalg.inv(sigma) * one) / (one.T * np.linalg.inv(sigma) * one)

    #print(np.sum(w_star))

    return  w_star

def realized_portfolio_returns(returns, w):

    w = np.asarray(w).T

    #print(returns)

    #print(w)

    portfolio_returns = returns *  w

    #print(portfolio_returns)

    #print(portfolio_returns.shape)

    whole_portfolio_returns = np.sum(portfolio_returns, axis=1)

    return_mean = whole_portfolio_returns.mean()

    return_var = whole_portfolio_returns.var()

    sharpe = (return_mean / np.sqrt(return_var)) * np.sqrt(252)

    portfolio_value = [100]

    for r in whole_portfolio_returns:

        portfolio_value.append(portfolio_value[-1] * (1 + r))

    print("sharpe ratio: " + str(sharpe))
    print("r var: " + str(return_var))
    print("-----")

    return portfolio_value

def exp_dist(x_1, x_2):
    dist = np.absolute(x_1 - x_2)
    sim = np.exp(-1 * np.square(dist))

    return sim

def get_similarities_cov(mat, feature_data, sim_function, feature_wise):


    flat_upper = mat[np.triu_indices(mat.shape[0], k=1)]
    cov_mean = flat_upper.mean()
    cov_demean = flat_upper - cov_mean

    n = feature_data.shape[0]

    if feature_wise:

        similarities = []

        for i in range(n):
            features_i = feature_data[i, :]
            for j in range(i + 1, n):
                features_j = feature_data[j, :]
                pairwise_sim = sim_function(features_i, features_j)
                similarities.append(pairwise_sim)

        similarities = np.stack(similarities)

    else:
        similarities = sim_function(feature_data)
        similarities = similarities[np.triu_indices(similarities.shape[0], k=1)]

    return similarities, cov_demean

def predict_covariance_matrix_model(model, scaler, feature_data, mean_var, mean_cov):

    #for feature wise:
    #sim_measure = lambda x_1, x_2: model.predict(scaler.transform(exp_dist(x_1, x_2).reshape(1, -1)))

    #for pairwise
    sim_measure = lambda x_1,x_2 : model.predict(scaler.transform(cosine_similarity(x_1.reshape(1,-1),x_2.reshape(1,-1))))

    matrix = pairwise_distances(feature_data, metric=sim_measure)
    matrix = matrix + mean_cov
    np.fill_diagonal(matrix, mean_var)

    return matrix


def print_mean_variance(cov):

    cov = cov.flatten()

    print("---------")

    print(cov.mean())

    print(cov.var())


#loading data
df_reports = pd.read_csv("data/reports_with_duplicates_final.csv", dtype="string", index_col="date")
df_reports.index = pd.to_datetime(df_reports.index)
df_returns = pd.read_csv("data/stock_returns.csv", index_col="Date")
df_returns.index = pd.to_datetime(df_returns.index)


#defining train test split
train_first = datetime(year=2005, month=12, day=31)
train_last = datetime(year=2018, month=9, day=30)


#checking if model has been saved
if os.path.isfile("vectorizer.p"):
    vectorizer = pickle.load(open("vectorizer.p", "rb"))
else:
    vectorizer = train_tfidf_model(df_reports, train_last)
    pickle.dump(vectorizer, open("vectorizer.p", "wb"))




#df_reports_test = df_reports.loc[test_first:test_last]
df_reports_train = df_reports.loc[train_first:train_last]
train_range = df_reports_train.index

train_x = []
train_y = []
mean_covs = []
mean_sims = []

for date in train_range:

    print(date)

    #if datetime(year=2008, month=6, day=30) <= date <= datetime(year=2009, month=3, day=31):
    #    continue
    #returns_stop = date + pd.tseries.offsets.QuarterEnd()
    returns_stop = date + pd.Timedelta(weeks=52)

    reports = get_reports_for_date(df_reports, date)
    returns = get_returns_for_period(df_returns, date + pd.DateOffset(days=1), returns_stop)

    returns, reports = find_column_intersection([returns, reports])

    cov = predict_cov_sample(returns)

    #
    # TODO support for different feature types
    #
    reports_features = tfidf_features(reports, vectorizer)
    sim_pairwise, cov_upper_dig = get_similarities_cov(cov, reports_features, cosine_similarity, feature_wise=False)

    train_x.append(sim_pairwise)
    train_y.append(cov_upper_dig)
    mean_covs.append(cov.diagonal().mean())

    print(cov.diagonal().mean())

#creating the training data
train_x = np.concatenate(train_x, axis=0)
train_y = np.concatenate(train_y, axis=0)


#
# TODO: incorporation of different time horizons and multiple test intervals
#

#creating the reports and returns for the test. Includes sample (previous time frame used for empirical estimation) and the test set
returns_sample = get_returns_for_period(df_returns, datetime(year=2018, month=1, day=1), datetime(year=2018, month=12, day=31))
returns_out_of_sample = get_returns_for_period(df_returns, datetime(year=2019, month=1, day=1), datetime(year=2019, month=3, day=31))

reports_sample = get_reports_for_date(df_reports, datetime(year=2017, month=12, day=31))
reports_out_of_sample = get_reports_for_date(df_reports, datetime(year=2018, month=12, day=31))

returns_sample, returns_out_of_sample, reports_sample, reports_out_of_sample = find_column_intersection([returns_sample, returns_out_of_sample, reports_sample, reports_out_of_sample])


#
# TODO: needs to be varied for feature wise similarities
#
#standardizing the data
scaler = StandardScaler()
train_x = train_x.reshape(-1,1)
train_x = scaler.fit_transform(train_x)

#regression model for prediction
lr = LinearRegression(fit_intercept=False)
lr.fit(train_x, train_y)

#mean variance in the sample, as model doesn't predict variance
sample_mean_var = np.mean(mean_covs)


#
# TODO: should incorporate different time horizons
#

#feature engineer for the time frame to predict
reports_features_out_of_sample = tfidf_features(reports_out_of_sample, vectorizer)

#different covariance matrix predictions
cov_sample = predict_cov_sample(returns_sample)

cov_upper = cov[np.triu_indices(cov.shape[0], k=1)]
sample_mean_cov = cov_upper.mean()
cov_model = predict_covariance_matrix_model(lr, scaler, reports_features_out_of_sample, sample_mean_var, sample_mean_cov)

cov_equal = np.full(cov_sample.shape, sample_mean_cov)
np.fill_diagonal(cov_equal, sample_mean_var)

LW = LedoitWolf()
cov_lw = LW.fit(returns_sample).covariance_

cov_combined = (cov_model +cov_lw) / 2

#empirical variance for the out of sample time frame
cov_true = compute_cov_matrix(returns_out_of_sample)


#evaluation of the predictions
print("--------eval-------- ")

print("frobenius norm for cov equal")
print(np.linalg.norm(cov_true - cov_equal, ord="fro"))

print("frobenius norm for sample cov")
print(np.linalg.norm(cov_true - cov_sample, ord="fro"))

print("frobenius norm for ledoit wolf estimator")
print(np.linalg.norm(cov_true - cov_lw, ord="fro"))

print("frobenius norm using nlu model on risk reports")
print(np.linalg.norm(cov_true - cov_model, ord="fro"))

print("frobenius norm of combined estimates of lw and model")
print(np.linalg.norm(cov_true - cov_combined, ord="fro"))

#constructing portfolios based on predictions
w_equal = optimal_portfolio_weights(cov_equal)
w_sample = optimal_portfolio_weights(cov_sample)
w_lw = optimal_portfolio_weights(cov_lw)
w_model = optimal_portfolio_weights(cov_model)
w_combined = optimal_portfolio_weights(cov_combined)

#calculating realized returns based on these portfolios
print("-----compute returns----")

print("equal cov portfolio")
r_equal = realized_portfolio_returns(returns_out_of_sample.values, w_equal)
print("sample cov portfolio")
r_sample = realized_portfolio_returns(returns_out_of_sample.values, w_sample)
print("ledoit wolf cov portfolio")
r_lw = realized_portfolio_returns(returns_out_of_sample.values, w_lw)
print("model cov portfolio")
r_model = realized_portfolio_returns(returns_out_of_sample.values, w_model)
print("combined cov portfolio")
r_combined = realized_portfolio_returns(returns_out_of_sample.values, w_combined)

#plotting the returns
x = range(len(r_equal))
plt.plot(x, r_equal, label="market")
plt.plot(x, r_sample, label="sample")
plt.plot(x, r_lw, label="ledoit wolf")
plt.plot(x, r_model, label="lda model")
plt.plot(x, r_combined, label="combined")

plt.legend()

plt.show()