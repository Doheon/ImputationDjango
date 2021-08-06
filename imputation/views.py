# from typing_extensions import ParamSpecArgs
from django.shortcuts import render
from django.http.response import HttpResponse

from module.naomi import NAMOIimputation
from module.brits import BRITSimputation

import pandas as pd
import numpy as np

import json
import os


import torch
def index(request):
    return render(request, 'index.html')


modelDic = {}
def getModel(uid, method=None, dataframe = None, window_size = None):
    if uid in modelDic:
        return modelDic[uid]

    if method=="NAOMI":
        modelDic[uid] = (NAMOIimputation(dataframe = dataframe, window_size=window_size), "NAOMI")
    elif method=="BRITS":
        modelDic[uid] = (BRITSimputation(dataframe = dataframe), "BRITS")
    else:
        find = autoFind(dataframe)
        if find:
            modelDic[uid] = (NAMOIimputation(dataframe = dataframe, window_size=len(dataframe)//10), "NAOMI")
        else:
            modelDic[uid] = (BRITSimputation(dataframe = dataframe), "BRITS")
    print(modelDic)
    return modelDic[uid]

def autoFind(dataframe):
    maxnull = 0
    cur = 0
    for i in range(len(dataframe)):
        if dataframe["value"].iloc[i] == "NaN" or pd.isnull(dataframe["value"].iloc[i]):
            cur += 1
            maxnull = max(maxnull, cur)
        else:
            cur = 0
    return maxnull>10

def imputeProcess(request):
    uid = request.POST["uid"]
    model, method = getModel(uid)
    if method=="NAOMI":
        model.optimizer = torch.optim.Adam(
                        filter(lambda p: p.requires_grad, model.model.parameters()), lr=7e-4)
        model.run_epoch(True, model.model, model.train_data, 10, model.optimizer, batch_size = 64, teacher_forcing=True)

        result = model.predict_result()
        result = model.scaler.inverse_transform(result.reshape(-1,1)).squeeze()
        result = result.tolist()
        label = model.df["time"].values.tolist()
        dic = {"label":label, "value": result}
        return HttpResponse(json.dumps(dic), content_type = "application/json")
    elif method=="BRITS":
        model.run_one_epoch()
        result = model.predict_result()
        result = result.tolist()
        label = model.df["time"].values.tolist()
        dic = {"label":label, "value": result}
        return HttpResponse(json.dumps(dic), content_type = "application/json")

def imputation(request):
    if len(request.FILES) == 0:
        return
    file = request.FILES["getCSV"]
    window_size = int(request.POST["windowsize"])
    method = request.POST["method"]
    uid = request.POST["uid"]

    df = pd.read_csv(file)
    df = df.fillna("NaN")

    model, method = getModel(uid, method, df, window_size)
    
    if method=="NAOMI":
        model.imputation(1)
        result_df = model.df
        result = model.scaler.inverse_transform(result_df["value"].values.reshape(-1,1)).squeeze()
        result = result.tolist()
        label = result_df["time"].values.tolist()
        dic = {"label":label, "value": result}
        return HttpResponse(json.dumps(dic), content_type = "application/json")
    elif method=="BRITS":
        result = model.imputation(1)
        result_df = model.df
        result = result.tolist()
        label = result_df["time"].values.tolist()
        dic = {"label":label, "value": result}
        return HttpResponse(json.dumps(dic), content_type = "application/json")


def visualize(request):
    if len(request.FILES) == 0:
        return
    file = request.FILES["getCSV"]
    df = pd.read_csv(file)
    df = df.fillna("NaN")
    result = df["value"].values.tolist()
    label = df["time"].values.tolist()
    dic = {"label":label, "value": result}
    return HttpResponse(json.dumps(dic), content_type = "application/json")


def save(request):
    uid = request.POST["uid"]
    model, method = getModel(uid)
    result_df = model.df.copy()
    result = model.predict_result()
    if method == "NAOMI":
        result = model.scaler.inverse_transform(result.reshape(-1,1)).squeeze()
    result_df["value"] = result
    src = "media/result_" + uid + ".csv"
    result_df.to_csv(src)
    dic = {"src" : src}
    return HttpResponse(json.dumps(dic), content_type = "application/json")

def delete(request):
    uid = request.POST["uid"]
    file = "media/result_" + uid + ".csv"
    
    if os.path.isfile(file):
        os.remove(file)
    if uid in modelDic:
        del(modelDic[uid])
    dic = {"ret":True}
    return  HttpResponse(json.dumps(dic), content_type = "application/json")