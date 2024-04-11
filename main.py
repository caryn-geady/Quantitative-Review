#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Nov 29 2023
Last updated Feb 23 2024

@author: caryn-geady
"""



# %% IMPORTS
# Change working directory to be whatever directory this script is in
import os
os.chdir(os.path.dirname(__file__))
import numpy as np, pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from matplotlib.lines import Line2D

# custom functions
import Code.misc_splitting as ms
import Code.lesion_selection as ls
import Code.lesion_aggregation as la
import Code.feature_handling as fh
import Code.survival_analysis as sa
     

# %% DATA LOADING

# SARC021
sarc021_radiomics = pd.read_csv('Data/SARC021/SARC021_radiomics.csv')
sarc021_clinical = pd.read_csv('Data/SARC021/SARC021_clinical.csv')

# optional ? -- look only at those patients with 2+ lesions contoured
id_counts = sarc021_radiomics['USUBJID'].value_counts()
valid_ids = id_counts[id_counts >= 2].index
sarc021_radiomics = sarc021_radiomics[sarc021_radiomics['USUBJID'].isin(valid_ids)].reset_index()
sarc021_clinical = sarc021_clinical[sarc021_clinical['USUBJID'].isin(valid_ids)].reset_index()

# RADCURE
radcure_radiomics = pd.read_csv('Data/RADCURE/RADCURE_radiomics.csv')
radcure_clinical = pd.read_csv('Data/RADCURE/RADCURE_clinical.csv')
# radcure_clinicalIso = radcure_clinical[np.unique(radcure_radiomics.USUBJID)[0]]

# CRLM 
crlm_radiomics = pd.read_csv('Data/TCIA-CRLM/CRLM_radiomics.csv')
crlm_clinical = pd.read_csv('Data/TCIA-CRLM/CRLM_clinical.csv')


# %% ANALYSIS

dataName = 'crlm'
aggName = 'UWA'
inclMetsFlag = False
rfFlag = True
uniFlag = False
shuffleFlag = False
numfeatures = 10
minLesions = 2

print('----------')
print(dataName, ' - ', aggName)
print('----------')

data_dict = {
                'radcure' : [radcure_radiomics,radcure_clinical],
                'sarc021' : [sarc021_radiomics,sarc021_clinical],
                'crlm'    : [crlm_radiomics,crlm_clinical]
        }

df_imaging, df_clinical = data_dict[dataName][0],data_dict[dataName][1]

id_counts = df_imaging['USUBJID'].value_counts()
valid_ids = id_counts[id_counts >= minLesions].index
df_imaging = df_imaging[df_imaging['USUBJID'].isin(valid_ids)].reset_index()
df_clinical = df_clinical[df_clinical['USUBJID'].isin(valid_ids)].reset_index()

if shuffleFlag:
    df_clinical['T_OS'] = df_clinical['T_OS'].sample(frac=1).reset_index(drop=True)
    df_clinical['E_OS'] = df_clinical['E_OS'].sample(frac=1).reset_index(drop=True)

if uniFlag:
    # print univariate results
    sa.univariate_CPH(df_imaging,df_clinical,mod_choice='total')
    sa.univariate_CPH(df_imaging,df_clinical,mod_choice='max')

if dataName == 'sarc021':
    train,test,val = ms.singleInstValidationSplit(df_imaging,df_clinical,0.8)
else:
    train,test = ms.randomSplit(df_imaging,df_clinical,0.8,False,False)
    val = np.nan

pipe_dict = {
                'train' : [train,True],
                'test'  : [test,False],
                'val'   : [val,False]
    }

func_dict = {
                'largest'  : [ls.selectLargestLesion, lambda x: fh.featureSelection(fh.featureReduction(x,numMetsFlag=inclMetsFlag,scaleFlag=True),numFeatures=numfeatures,numMetsFlag=inclMetsFlag)],
                'smallest' : [ls.selectSmallestLesion, lambda x: fh.featureSelection(fh.featureReduction(x,numMetsFlag=inclMetsFlag,scaleFlag=True),numFeatures=numfeatures,numMetsFlag=inclMetsFlag)],
                'primary'  : [ls.selectPrimaryTumor, lambda x: fh.featureSelection(fh.featureReduction(x,numMetsFlag=inclMetsFlag,scaleFlag=True),numFeatures=numfeatures,numMetsFlag=inclMetsFlag)],
                'lung'     : [ls.selectLargestLungLesion, lambda x: fh.featureSelection(fh.featureReduction(x,numMetsFlag=inclMetsFlag,scaleFlag=True),numFeatures=numfeatures,numMetsFlag=inclMetsFlag)],
                'UWA'      : [la.calcUnweightedAverage, lambda x: fh.featureSelection(fh.featureReduction(x,numMetsFlag=inclMetsFlag,scaleFlag=True),numFeatures=numfeatures,numMetsFlag=inclMetsFlag)],
                'VWA'      : [la.calcVolumeWeightedAverage, lambda x: fh.featureSelection(fh.featureReduction(x,numMetsFlag=inclMetsFlag,scaleFlag=True),numFeatures=numfeatures,numMetsFlag=inclMetsFlag)],
                'VWANLrg'  : [la.calcVolumeWeightedAverageNLargest, lambda x: fh.featureSelection(fh.featureReduction(x,numMetsFlag=inclMetsFlag,scaleFlag=True),numFeatures=numfeatures,numMetsFlag=inclMetsFlag)],
                'cosine'   : [la.calcCosineMetrics, lambda x: x],
                'concat'   : [la.concatenateNLargest, lambda x: fh.featureSelection(fh.featureReduction(x,varOnly=True))]
    }
    
# ----- TRAINING -----
df_imaging_train = df_imaging[df_imaging.USUBJID.isin(pipe_dict['train'][0])].reset_index()
df_clinical_train = df_clinical[df_clinical.USUBJID.isin(pipe_dict['train'][0])].reset_index()

print('feature selection')
trainingSet = func_dict[aggName][1](func_dict[aggName][0](df_imaging_train,df_clinical_train,numMetsFlag=inclMetsFlag).drop('USUBJID',axis=1))
print('----------')
# ----- TESTING -----
df_imaging_test = df_imaging[df_imaging.USUBJID.isin(pipe_dict['test'][0])].reset_index()
df_clinical_test = df_clinical[df_clinical.USUBJID.isin(pipe_dict['test'][0])].reset_index()

testingSet = func_dict[aggName][0](df_imaging_test,df_clinical_test,scaleFlag=True,numMetsFlag=inclMetsFlag).drop('USUBJID',axis=1)[trainingSet.columns]

best_params_CPH, scores_CPH = sa.CPH_bootstrap(trainingSet,aggName,'OS',pipe_dict['train'][1])
sa.CPH_bootstrap(testingSet,aggName,'OS',pipe_dict['test'][1],param_grid=best_params_CPH)

best_params_LAS, scores_LAS = sa.LASSO_COX_bootstrap(trainingSet,aggName,'OS',pipe_dict['train'][1])
sa.LASSO_COX_bootstrap(testingSet,aggName,'OS',pipe_dict['test'][1],param_grid=best_params_LAS)

if rfFlag:
    best_params_RSF, scores_RSF = sa.RSF_bootstrap(trainingSet,aggName,'OS',pipe_dict['train'][1])
    sa.RSF_bootstrap(testingSet,aggName,'OS',pipe_dict['test'][1],param_grid=best_params_RSF)

if dataName == 'sarc021':
    # ----- VALIDATION -----
    print('----------')
    print('validation')
    df_imaging_val = df_imaging[df_imaging.USUBJID.isin(pipe_dict['val'][0])].reset_index()
    df_clinical_val = df_clinical[df_clinical.USUBJID.isin(pipe_dict['val'][0])].reset_index()

    validationSet = func_dict[aggName][0](df_imaging_val,df_clinical_val,scaleFlag=True,numMetsFlag=inclMetsFlag).drop('USUBJID',axis=1)[trainingSet.columns]

    sa.CPH_bootstrap(validationSet,aggName,'OS',pipe_dict['val'][1],param_grid=best_params_CPH)
    sa.LASSO_COX_bootstrap(validationSet,aggName,'OS',pipe_dict['val'][1],param_grid=best_params_LAS)
    
    if rfFlag:
        sa.RSF_bootstrap(validationSet,aggName,'OS',pipe_dict['val'][1],param_grid=best_params_RSF)

if np.logical_and(aggName == 'largest',inclMetsFlag):
    aggName = 'largest+'

# save results to file
# ms.add_column_to_csv('Results/'+dataName+'_min'+str(numLesions)+'_CPH.csv', aggName, scores_CPH)
# ms.add_column_to_csv('Results/'+dataName+'_min'+str(numLesions)+'_LAS.csv', aggName, scores_LAS)
# ms.add_column_to_csv('Results/'+dataName+'_min'+str(numLesions)+'_RSF.csv', aggName, scores_RSF)



# %% PLOTTING/SAVING DATA

dataName = 'radcure'
modelName = 'CPH'
numLesions = 1
# univariate results for total volume of all ROIs and OS
uni_dict = {
            'radcure' : 0.632,
            'crlm'    : 0.585,
            'sarc021' : 0.607}

# load data
all_data = pd.read_csv('Results/'+dataName+'_min'+str(numLesions)+'_'+modelName+'_training.csv')
test_df = pd.read_csv('Results/'+dataName+'_min'+str(numLesions)+'_'+modelName+'_testing.csv')

if dataName != 'radcure':
    all_data['primary'] = np.nan 
    test_df['primary'] = np.nan
if dataName != 'sarc021':
    all_data['lung'] = np.nan 
    test_df['lung'] = np.nan

all_data = all_data[['largest','largest+','smallest','primary','lung','VWANLrg','concat','UWA','VWA','cosine']]
all_data.columns = ['Largest','Largest+','Smallest','Primary','Lung','VWA N-largest','Concatenation','UWA','VWA','Cosine Similarity']
test_df = test_df[['largest','largest+','smallest','primary','lung','VWANLrg','concat','UWA','VWA','cosine']]
test_df.columns = ['Largest','Largest+','Smallest','Primary','Lung','VWA N-largest','Concatenation','UWA','VWA','Cosine Similarity']

# plotting params
my_pal = ['#4daf4a','#4daf4a','#4daf4a','#4daf4a','#4daf4a','#ff7f00','#ff7f00','#377eb8','#377eb8','#377eb8']
plt.rcParams.update({'font.size': 18})
plt.rcParams["font.family"] = "Avenir"

plt.axvline(x=uni_dict[dataName],linestyle='--',color='black')
ax = sns.violinplot(data=all_data,orient='h',palette=my_pal)
sns.stripplot(data=test_df,orient='h',edgecolor='black', linewidth=1, palette=['white'] * 4,ax=ax)

# Modify the legend
legend_elements = [Line2D([0], [0], linestyle='--', color='k', label='Total Volume'),
                   Line2D([0], [0], marker='s', color='w', label='Lesion Selection', markeredgecolor='k',markerfacecolor='#4daf4a', markersize=10,),
                   Line2D([0], [0], marker='s', color='w', label='Information from Select Lesions', markeredgecolor='k',markerfacecolor='#ff7f00', markersize=10),
                   Line2D([0], [0], marker='s', color='w', label='Information from All Lesions', markeredgecolor='k',markerfacecolor='#377eb8', markersize=10),
                   Line2D([0], [0], marker='o', color='w', label='Testing Data', markeredgecolor='k',markerfacecolor='w', markersize=8)]

plt.legend(handles=legend_elements, bbox_to_anchor=(1.05, 1), loc='upper left',fontsize=14)

plt.xlabel('Concordance Index (C-Index)')
plt.xlim([0.35,1])
plt.ylabel('Method')
# plt.title(dataName)
plt.savefig('Results/Figures/'+dataName+'_min'+str(numLesions)+'_'+modelName+'.png',dpi=300,bbox_inches='tight')
plt.show()

# %%

# from scipy.stats import tukey_hsd as tukey
# res = tukey(all_data.iloc[:,0],all_data.iloc[:,1],all_data.iloc[:,2],all_data.iloc[:,3],
#       all_data.iloc[:,4],all_data.iloc[:,5],all_data.iloc[:,6],all_data.iloc[:,7],
#       all_data.iloc[:,8],all_data.iloc[:,9])

#%% TESTING

# outcome = 'OS'
# numFeatures = 10
# df = reduced_crlm

# dup = df.copy()

# if 'E_'+outcome in dup.columns:
#     df_surv = dup.pop('E_'+outcome)
    
# if 'T_'+outcome in dup.columns:
#     df_surv = pd.concat((df_surv,dup.pop('T_'+outcome)),axis=1)

# x = dup.copy().iloc[:,:]
# # print('x shape: ', x.shape)

# if len(df_surv.shape)>1:
#     y = Surv.from_arrays(df_surv['E_OS'],df_surv['T_OS'])
#     # print(y)
# else:
#     y = df_surv.values
#     # print(y)

# selected_features = mrmr_classif(x,y,numFeatures,relevance='rf')
# # print('selected features: ',selected_features)

# df_Selected = pd.concat([df[selected_features],df_surv],axis=1)





# %%
# ------------------------ #
# Cox Proportional Hazards
# ------------------------ #
# CPH_bootstrap(UWA_top40_fp)
# CPH_bootstrap(WA_top40_fp)
# CPH_bootstrap(big3_top40_fp)
# CPH_bootstrap(big1_top40_fp)
# CPH_bootstrap(big1_top40_fp, num=True)
# CPH_bootstrap(smallest_top40_fp)

# #%%
# # ---------------------- #
# # Lasso-Cox
# # ---------------------- #
# LASSO_COX_bootstrap(UWA_top40_fp)
# LASSO_COX_bootstrap(WA_top40_fp)
# LASSO_COX_bootstrap(big3_top40_fp)
# LASSO_COX_bootstrap(big1_top40_fp)
# LASSO_COX_bootstrap(big1_top40_fp, num=True)
# LASSO_COX_bootstrap(smallest_top40_fp)

# # ----------------------- #
# # Random Survival Forest
# # ----------------------- #
# RSF_bootstrap(UWA_top40_fp)
# RSF_bootstrap(WA_top40_fp)
# RSF_bootstrap(big3_top40_fp)
# RSF_bootstrap(big1_top40_fp)
# RSF_bootstrap(big1_top40_fp, num=True)
# RSF_bootstrap(smallest_top40_fp)

# # -------------------- #
# # Sub-Analysis: Num Mets < 5, 5-10, 11+
# # -------------------- #

# df = pd.read_csv(UWA_top40_fp, index_col=0)

# # map labels to radiomic data
# df['nummets'] = df.index.to_series().map(nummetsdic)
# df['nummets'] = df['nummets'].astype(int)

# # create sub-groups
# df_5 = df.loc[df['nummets'] < 5].copy()
# df_5_10 = df.loc[(df['nummets'] >= 5) & (df['nummets'] <= 10)].copy()
# df_11 = df.loc[df['nummets'] >= 11].copy()

# CPH_bootstrap(UWA_top40_fp, sub=df_5)
# CPH_bootstrap(UWA_top40_fp, sub=df_5_10)
# CPH_bootstrap(UWA_top40_fp, sub=df_11)


# df = pd.read_csv(WA_top40_fp, index_col=0)

# # map labels to radiomic data
# df['nummets'] = df.index.to_series().map(nummetsdic)
# df['nummets'] = df['nummets'].astype(int)

# # create sub-groups
# df_5 = df.loc[df['nummets'] < 5].copy()
# df_5_10 = df.loc[(df['nummets'] >= 5) & (df['nummets'] <= 10)].copy()
# df_11 = df.loc[df['nummets'] >= 11].copy()

# CPH_bootstrap(WA_top40_fp, sub=df_5)
# CPH_bootstrap(WA_top40_fp, sub=df_5_10)
# CPH_bootstrap(WA_top40_fp, sub=df_11)

# df = pd.read_csv(big3_top40_fp, index_col=0)

# # map labels to radiomic data
# df['nummets'] = df.index.to_series().map(nummetsdic)
# df['nummets'] = df['nummets'].astype(int)

# # create sub-groups
# df_5 = df.loc[df['nummets'] < 5].copy()
# df_5_10 = df.loc[(df['nummets'] >= 5) & (df['nummets'] <= 10)].copy()
# df_11 = df.loc[df['nummets'] >= 11].copy()

# CPH_bootstrap(big3_top40_fp, sub=df_5)
# CPH_bootstrap(big3_top40_fp, sub=df_5_10)
# CPH_bootstrap(big3_top40_fp, sub=df_11)

# df = pd.read_csv(big1_top40_fp, index_col=0)

# # map labels to radiomic data
# df['nummets'] = df.index.to_series().map(nummetsdic)
# df['nummets'] = df['nummets'].astype(int)

# # create sub-groups
# df_5 = df.loc[df['nummets'] < 5].copy()
# df_5_10 = df.loc[(df['nummets'] >= 5) & (df['nummets'] <= 10)].copy()
# df_11 = df.loc[df['nummets'] >= 11].copy()

# CPH_bootstrap(big1_top40_fp, sub=df_5)
# CPH_bootstrap(big1_top40_fp, sub=df_5_10)
# CPH_bootstrap(big1_top40_fp, sub=df_11)

# df = pd.read_csv(big1_top40_fp, index_col=0)

# # map labels to radiomic data
# df['nummets'] = df.index.to_series().map(nummetsdic)
# df['nummets'] = df['nummets'].astype(int)

# # create sub-groups
# df_5 = df.loc[df['nummets'] < 5].copy()
# df_5_10 = df.loc[(df['nummets'] >= 5) & (df['nummets'] <= 10)].copy()
# df_11 = df.loc[df['nummets'] >= 11].copy()

# CPH_bootstrap(big1_top40_fp, num=True, sub=df_5)
# CPH_bootstrap(big1_top40_fp, num=True, sub=df_5_10)
# CPH_bootstrap(big1_top40_fp, num=True, sub=df_11)

# df = pd.read_csv(smallest_top40_fp, index_col=0)

# # map labels to radiomic data
# df['nummets'] = df.index.to_series().map(nummetsdic)
# df['nummets'] = df['nummets'].astype(int)

# # create sub-groups
# df_5 = df.loc[df['nummets'] < 5].copy()
# df_5_10 = df.loc[(df['nummets'] >= 5) & (df['nummets'] <= 10)].copy()
# df_11 = df.loc[df['nummets'] >= 11].copy()

# CPH_bootstrap(smallest_top40_fp, sub=df_5)
# CPH_bootstrap(smallest_top40_fp, sub=df_5_10)
# CPH_bootstrap(smallest_top40_fp, sub=df_11)

# # -------------------- #
# # Sub-Analysis: Volume Largest Met <200, 200-700, >700
# # -------------------- #

# df = pd.read_csv(UWA_top40_fp, index_col=0)

# # map labels to radiomic data
# df['volume'] = df.index.to_series().map(big1voldic)
# df['volume'] = df['volume'].astype(int)

# # create sub-groups
# df_200 = df.loc[df['volume'] < 200].copy()
# df_200_700 = df.loc[(df['volume'] >= 200) & (df['volume'] <= 700)].copy()
# df_700 = df.loc[df['volume'] >= 700].copy()

# CPH_bootstrap(UWA_top40_fp, sub=df_200)
# CPH_bootstrap(UWA_top40_fp, sub=df_200_700)
# CPH_bootstrap(UWA_top40_fp, sub=df_700)

# df = pd.read_csv(WA_top40_fp, index_col=0)

# # map labels to radiomic data
# df['volume'] = df.index.to_series().map(big1voldic)
# df['volume'] = df['volume'].astype(int)

# # create sub-groups
# df_200 = df.loc[df['volume'] < 200].copy()
# df_200_700 = df.loc[(df['volume'] >= 200) & (df['volume'] <= 700)].copy()
# df_700 = df.loc[df['volume'] >= 700].copy()

# CPH_bootstrap(WA_top40_fp, sub=df_200)
# CPH_bootstrap(WA_top40_fp, sub=df_200_700)
# CPH_bootstrap(WA_top40_fp, sub=df_700)

# df = pd.read_csv(big3_top40_fp, index_col=0)

# # map labels to radiomic data
# df['volume'] = df.index.to_series().map(big1voldic)
# df['volume'] = df['volume'].astype(int)

# # create sub-groups
# df_200 = df.loc[df['volume'] < 200].copy()
# df_200_700 = df.loc[(df['volume'] >= 200) & (df['volume'] <= 700)].copy()
# df_700 = df.loc[df['volume'] >= 700].copy()

# CPH_bootstrap(big3_top40_fp, sub=df_200)
# CPH_bootstrap(big3_top40_fp, sub=df_200_700)
# CPH_bootstrap(big3_top40_fp, sub=df_700)

# df = pd.read_csv(big1_top40_fp, index_col=0)

# # map labels to radiomic data
# df['volume'] = df.index.to_series().map(big1voldic)
# df['volume'] = df['volume'].astype(int)

# # create sub-groups
# df_200 = df.loc[df['volume'] < 200].copy()
# df_200_700 = df.loc[(df['volume'] >= 200) & (df['volume'] <= 700)].copy()
# df_700 = df.loc[df['volume'] >= 700].copy()

# CPH_bootstrap(big1_top40_fp, sub=df_200)
# CPH_bootstrap(big1_top40_fp, sub=df_200_700)
# CPH_bootstrap(big1_top40_fp, sub=df_700)

# df = pd.read_csv(big1_top40_fp, index_col=0)

# # map labels to radiomic data
# df['volume'] = df.index.to_series().map(big1voldic)
# df['volume'] = df['volume'].astype(int)

# # create sub-groups
# df_200 = df.loc[df['volume'] < 200].copy()
# df_200_700 = df.loc[(df['volume'] >= 200) & (df['volume'] <= 700)].copy()
# df_700 = df.loc[df['volume'] >= 700].copy()

# CPH_bootstrap(big1_top40_fp, num=True, sub=df_200)
# CPH_bootstrap(big1_top40_fp, num=True, sub=df_200_700)
# CPH_bootstrap(big1_top40_fp, num=True, sub=df_700)

# df = pd.read_csv(smallest_top40_fp, index_col=0)

# # map labels to radiomic data
# df['volume'] = df.index.to_series().map(big1voldic)
# df['volume'] = df['volume'].astype(int)

# # create sub-groups
# df_200 = df.loc[df['volume'] < 200].copy()
# df_200_700 = df.loc[(df['volume'] >= 200) & (df['volume'] <= 700)].copy()
# df_700 = df.loc[df['volume'] >= 700].copy()

# CPH_bootstrap(smallest_top40_fp, sub=df_200)
# CPH_bootstrap(smallest_top40_fp, sub=df_200_700)
# CPH_bootstrap(smallest_top40_fp, sub=df_700)

