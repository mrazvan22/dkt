import os
import sys
import numpy as np
import math
from auxFunc import *
import scipy
#import scipy.cluster.hierarchy
import pickle
import gc
from matplotlib import pyplot as pl
import Plotter
import copy
import colorsys

import DisProgBuilder

class JMDBuilderOnePass(DisProgBuilder.DPMBuilder):
  # builds a Joint Disease model

  def __init__(self, unitModelObjList, disModelObj, priorsUnitModels, priorsDisModels):
    self.unitModelObjList = unitModelObjList
    self.disModelObj = disModelObj
    self.priorsUnitModels = priorsUnitModels
    self.priorsDisModels = priorsDisModels

  def generate(self, dataIndices, expName, params):
    return JDMOnePass(dataIndices, expName, params,
      self.unitModelObjList, self.disModelObj, self.priorsUnitModels, self.priorsDisModels)

class JDMOnePass(DisProgBuilder.DPMInterface):

  def __init__(self, dataIndices, expName, params, unitModelObjList, disModelObj, priorsUnitModels, priorsDisModels):
    self.dataIndices = dataIndices
    self.expName = expName
    self.params = params
    self.outFolder = params['outFolder']
    os.system('mkdir -p %s' % self.outFolder)
    self.params['plotTrajParams']['outFolder'] = self.outFolder
    self.params['plotTrajParams']['expName'] = expName
    self.nrBiomk = len(params['X'])
    self.nrFuncUnits = params['nrFuncUnits']
    self.biomkInFuncUnit = params['biomkInFuncUnit']

    self.unitModels = None # functional unit models
    self.disModels = None # disease specific models

    disLabels = self.params['disLabels']
    self.nrDis = len(disLabels)

    self.binMaskSubjForEachDisD = params['binMaskSubjForEachDisD']

    self.unitModelObjList = unitModelObjList
    self.disModelObj = disModelObj

    self.priorsUnitModels = priorsUnitModels
    self.priorsDisModels = priorsDisModels

  def runStd(self, runPart):
    self.run(runPart)

  def run(self, runPart):
    filePath = '%s/unitModels.npz' % self.outFolder


    if runPart[0] == 'R':
      nrGlobIterUnit = self.params['nrGlobIterUnit']

      Xfilt, Yfilt, visitIndicesFilt = filterDataListFormat(self.params, self.dataIndices)

      self.unitModels = [_ for _ in range(self.nrFuncUnits)]

      # functional units
      for u in range(self.nrFuncUnits):
        plotTrajParamsFuncUnit = JDMOnePass.createPlotTrajParamsFuncUnit(self.params, unitNr=u)
        plotterObjCurrFuncUnit = Plotter.PlotterFuncUnit(plotTrajParamsFuncUnit)  # set separate plotter for the

        XfiltCurrUnit = [Xfilt[b] for b in self.biomkInFuncUnit[u]]
        YfiltCurrUnit = [Yfilt[b] for b in self.biomkInFuncUnit[u]]
        # print(len(XfiltCurrUnit))
        # print(dads)
        visitIndicesCurrUnit = [visitIndicesFilt[b] for b in self.biomkInFuncUnit[u]]
        outFolderCurrUnit = '%s/unit%d' % (self.outFolder, u)
        os.system('mkdir -p %s' % outFolderCurrUnit)
        self.unitModels[u] = self.unitModelObjList[u](XfiltCurrUnit, YfiltCurrUnit, visitIndicesCurrUnit, outFolderCurrUnit,
          plotterObjCurrFuncUnit, plotTrajParamsFuncUnit['labels'], self.params)
        self.unitModels[u].priors = self.priorsUnitModels[u]

        self.unitModels[u].Optimize(nrGlobIterUnit, Plot=True)

      pickle.dump(self.unitModels, open(filePath, 'wb'), protocol = pickle.HIGHEST_PROTOCOL)
    else:
      self.unitModels = pickle.load(open(filePath, 'rb'))

      # make sure the data you used has not been changed since fitting this model
      for b in range(len(self.unitModels[0].X)):
        # print('--------------- b', b)
        idxInAllBiomk = self.biomkInFuncUnit[0][b]
        for s in range(len(self.unitModels[0].X[b])):
          assert np.all(self.unitModels[0].X[b][s] == self.params['X'][idxInAllBiomk][s])
          assert np.all(self.unitModels[0].Y[b][s] == self.params['Y'][idxInAllBiomk][s])

      # for u in range(self.nrFuncUnits):
      #   plotTrajParamsFuncUnit = JDMOnePass.createPlotTrajParamsFuncUnit(self.params, unitNr=u)
      #   plotterObjCurrFuncUnit = Plotter.PlotterFuncUnit(plotTrajParamsFuncUnit)  # set separate plotter for the


    disModelsFile = '%s/disModels.npz' % self.outFolder
    nrSubj = self.unitModels[0].nrSubj

    # for s in range(len(self.params['X'][0])):
    #   entriesCurrSubj = [self.params['X'][b][s].shape[0] > 0 for b in range(30)]
    #   nrEntriesPerSubj = np.sum(entriesCurrSubj)
    #   if nrEntriesPerSubj == 0:
    #     print(s, entriesCurrSubj)
    #     print(dadsa)

    # print(labels)
    # print(dasda)

    if runPart[1] == 'R':
      nrGlobIterDis = self.params['nrGlobIterDis']
      dysfuncScoresU = [0 for x in range(self.nrFuncUnits)]
      xDysfunSubjU = [0 for x in range(self.nrFuncUnits)]

      minDys = np.zeros(self.nrFuncUnits)
      maxDys = np.zeros(self.nrFuncUnits)

      for u in range(self.nrFuncUnits):
        dysfuncScoresU[u] = [[] for _ in range(nrSubj)]
        xDysfunSubjU[u] = [[] for _ in range(nrSubj)]

        XshiftedUnitModel, XunitModel, YunitModel, _ = self.unitModels[u].getData()

        for sub in range(self.unitModels[u].nrSubj):
          for b in range(self.unitModels[u].nrBiomk):
            xDysfunSubjUCurrSubj = XunitModel[b][sub]  # Xs in the unit model
            xDysfunSubjU[u][sub] += list(xDysfunSubjUCurrSubj)
            dysfuncScoresU[u][sub] += list(XshiftedUnitModel[b][sub]) # (Xs + timeShift) in the unit model

          xDysfunSubjU[u][sub] = np.sort(np.unique(xDysfunSubjU[u][sub]))
          dysfuncScoresU[u][sub] = np.sort(np.unique(dysfuncScoresU[u][sub]))

          # assert len(dysfuncScoresU[u][sub]) == len(xDysfunSubjU[u][sub])
          # if dysfuncScoresU[u][sub].shape[0] == 0:
          #   print('u, sub', u, sub)
          #   print('dysfuncScoresU[u][sub]', dysfuncScoresU[u][sub])
          #   print('self.unitModels[u].nrBiomk', self.unitModels[u].nrBiomk)
          #   print('XshiftedUnitModel[b][sub]', [XshiftedUnitModel[b][sub] for b in range(self.unitModels[u].nrBiomk)])
          #   print(dasda)

        dysfuncScoresSerial = [x2 for x in dysfuncScoresU[u] for x2 in x]
        minDys[u] = np.min(dysfuncScoresSerial)
        maxDys[u] = np.max(dysfuncScoresSerial)

        # make the functional scores be between [0,1]
        # 26/02/18: actually this is not needed, re-scaling will be done in the plotting
        # 2 June 2018: actually I need this, otherwise the plotting of unit-traj in dis space
        # will have wrong Y-scale
        dysfuncScoresU[u] = [self.unitModels[u].applyScalingXzeroOneFwd(xs) for xs in dysfuncScoresU[u]]


      # now build separate model for each disease
      disLabels = self.params['disLabels']
      nrDis = len(disLabels)
      self.disModels = [_ for _ in range(nrDis)]

      informPriorTrajDisModels = [True, False] # make informed prior only for the first disease
      for disNr in range(nrDis):
        # nrBiomkDisModel = len(xDysfunSubjU) + len(self.params['otherBiomkPerDisease'][disNr])
        nrBiomkDisModel = self.nrFuncUnits

        xDysfunSubjUCopy = copy.deepcopy(xDysfunSubjU)
        dysfuncScoresUCopy = copy.deepcopy(dysfuncScoresU)

        # if 'otherBiomkPerDisease' in self.params.keys():
        #   xDysfunSubjUCopy += [self.params['X'][i] for i in self.params['otherBiomkPerDisease'][disNr]]
        #   dysfuncScoresUCopy += [self.params['Y'][i] for i in self.params['otherBiomkPerDisease'][disNr]]


        # first filter the data .. keep only subj in current disease
        xDysfunSubjCurrDisUSX = [_ for _ in range(nrBiomkDisModel)]
        dysfuncScoresCurrDisUSX = [_ for _ in range(nrBiomkDisModel)]
        visitIndicesCurrDisUSX = [[] for b in range(nrBiomkDisModel)]

        subjIndCurrDis = np.where(self.binMaskSubjForEachDisD[disNr])[0]
        for b in range(nrBiomkDisModel):
          xDysfunSubjCurrDisUSX[b] = [xDysfunSubjUCopy[b][s] for s in
            subjIndCurrDis]
          dysfuncScoresCurrDisUSX[b] = [dysfuncScoresUCopy[b][s] for s in
            subjIndCurrDis]

          visitIndicesCurrDisUSX[b] = [_ for _ in range(len(xDysfunSubjCurrDisUSX[b]))]
          for s in range(len(xDysfunSubjCurrDisUSX[b])):
            visitIndicesCurrDisUSX[b][s] = np.array(range(xDysfunSubjCurrDisUSX[b][s].shape[0]))

        for s in range(len(self.params['X'])):
          assert [self.params['X'][b2][subjIndCurrDis[s]] for b2 in range(self.params['nrBiomk'])]

        for b in range(self.nrFuncUnits - self.params['nrExtraBiomk']):
          for s in range(len(xDysfunSubjCurrDisUSX[b])):
            if xDysfunSubjCurrDisUSX[b][s].shape[0] == 0:
              print(xDysfunSubjCurrDisUSX[0][s])
              print([0 for b2 in range(nrBiomkDisModel)])
              print(xDysfunSubjCurrDisUSX)
              print([xDysfunSubjCurrDisUSX[b2] for b2 in range(nrBiomkDisModel)])
              print([xDysfunSubjCurrDisUSX[b2][0] for b2 in range(nrBiomkDisModel)])
              print(b, s, self.params['RID'][subjIndCurrDis[s]])
              print([xDysfunSubjCurrDisUSX[b2][s] for b2 in range(nrBiomkDisModel)])

              print([self.params['X'][b2][subjIndCurrDis[s]] for b2 in range(self.params['nrBiomk'])])
              print([self.params['Y'][b2][subjIndCurrDis[s]]  for b2 in range(self.params['nrBiomk'])])
              # import pdb
              # pdb.set_trace()
              raise ValueError('subj should contain dysfunction scores for all imaging functional units')

        plotTrajParamsDis = JDMOnePass.createPlotTrajParamsDis(self.params, disNr)
        plotterCurrDis = Plotter.PlotterDis(plotTrajParamsDis)  # set separate plotter for the

        outFolderCurDis = '%s/%s' % (self.outFolder, self.params['disLabels'][disNr])
        os.system('mkdir -p %s' % outFolderCurDis)
        self.disModels[disNr] = self.disModelObj(xDysfunSubjCurrDisUSX, dysfuncScoresCurrDisUSX, visitIndicesCurrDisUSX,
          outFolderCurDis, plotterCurrDis, plotTrajParamsDis['labels'], self.params)
        self.disModels[disNr].priors = self.priorsDisModels[disNr]
        # manually set limits on Y axis for the disease models
        self.disModels[disNr].min_yB = [0 for b in range(self.disModels[disNr].nrBiomk)]
        self.disModels[disNr].min_yB = [1 for b in range(self.disModels[disNr].nrBiomk)]
        self.disModels[disNr].Optimize(nrGlobIterDis, Plot=True)

        XshiftedScaledDBS, XdisDBSX, _, _ = self.disModels[disNr].getData(flagAllBiomkShouldBePresent=False)

      pickle.dump(self.disModels, open(disModelsFile, 'wb'), protocol = pickle.HIGHEST_PROTOCOL)

    elif runPart[1] == 'L':
      self.disModels = pickle.load(open(disModelsFile, 'rb'))

      # for disNr in range(self.nrDis):
      #   plotTrajParamsDis = JDMOnePass.createPlotTrajParamsDis(self.params, disNr)
      #   plotterCurrDis = Plotter.PlotterDis(plotTrajParamsDis)  # set separate plotter for the

        # fig = plotterCurrDis.plotTrajSameSpace(self.disModels[disNr])
        # fig.savefig('%s/%s_trajSameSpace_%s.png' % (self.outFolder, self.params['disLabels'][disNr],
        #   self.expName))

    res = None
    return res

  def predictBiomkSubjGivenXs(self, newXs, disNr):
    """
    predicts biomarkers for given xs (disease progression scores)

    :param newXs: newXs is an array as with np.linspace(minX-unscaled, maxX-unscaled)
    newXs will be scaled to the space of the gpProcess
    :param disNr: index of disease: 0 (tAD) or 1 (PCA)
    :return: biomkPredXB = Ys
    """

    # first predict the dysfunctionality scores in the disease specific model
    dysfuncPredXU = self.disModels[disNr].predictBiomk(newXs)


    # then predict the inidividual biomarkers in the disease agnostic models
    biomkPredXB = np.zeros((newXs.shape[0], self.nrBiomk))
    for u in range(self.nrFuncUnits):
      dysfScaled = self.unitModels[u].applyScalingXzeroOneInv(dysfuncPredXU[:,u])

      biomkPredXB[:, self.biomkInFuncUnit[u]] = \
        self.unitModels[u].predictBiomk(dysfScaled)


    biomkIndNotInFuncUnits = self.biomkInFuncUnit[-1]
    # assumes these biomarkers are at the end

    nrBiomkNotInUnit = len(biomkIndNotInFuncUnits)
    biomkPredXB[:, biomkIndNotInFuncUnits] = \
      dysfuncPredXU[:,dysfuncPredXU.shape[1] - nrBiomkNotInUnit :]

    print('dysfuncPredXU[:,0]', dysfuncPredXU[:,0])
    print('biomkPredXB[:,0]', biomkPredXB[:,0])
    # print(asds)

    return biomkPredXB

  def sampleBiomkTrajGivenXs(self, newXs, disNr, nrSamples):
    """
    predicts biomarkers for given xs (disease progression scores)

    :param newXs: newXs is an array as with np.linspace(minX-unscaled, maxX-unscaled)
    newXs will be scaled to the space of the gpProcess
    :param disNr: index of disease: 0 (tAD) or 1 (PCA)
    :param nrSamples:

    :return: biomkPredXB = Ys
    """

    # first predict the dysfunctionality scores in the disease specific model
    dysfuncPredXU = self.disModels[disNr].predictBiomk(newXs)

    # then predict the inidividual biomarkers in the disease agnostic models
    trajSamplesBXS = np.nan * np.ones((self.nrBiomk, newXs.shape[0], nrSamples))

    for u in range(self.nrFuncUnits):
      biomkIndInCurrUnit = self.biomkInFuncUnit[u]
      for b in range(biomkIndInCurrUnit.shape[0]):
        trajSamplesBXS[biomkIndInCurrUnit[b],:,:] = \
            self.unitModels[u].sampleTrajPost(dysfuncPredXU[:,u], b, nrSamples)


    biomkIndNotInFuncUnits = self.biomkInFuncUnit[-1]
    nrBiomkNotInUnit = biomkIndNotInFuncUnits.shape[0]

    # assumes these biomarkers are at the end
    indOfRealBiomk =  list(range(dysfuncPredXU.shape[1] - nrBiomkNotInUnit, dysfuncPredXU.shape[1]))
    for b in range(len(biomkIndNotInFuncUnits)):
      trajSamplesBXS[biomkIndNotInFuncUnits[b],:,:] = \
        self.disModels[disNr].sampleTrajPost(newXs, indOfRealBiomk[b], nrSamples)

    assert not np.isnan(trajSamplesBXS).any()

    return trajSamplesBXS

  @staticmethod
  def createPlotTrajParamsFuncUnit(params, unitNr):

    plotTrajParamsFuncUnit = copy.deepcopy(params['plotTrajParams'])
    plotTrajParamsFuncUnit['nrRows'] = params['plotTrajParams']['nrRowsFuncUnit']
    plotTrajParamsFuncUnit['nrCols'] = params['plotTrajParams']['nrColsFuncUnit']

    if 'trueParamsFuncUnits' in params.keys():
        # set the params for plotting true trajectories - the Xs and f(Xs), i.e. trueTraj
      plotTrajParamsFuncUnit['trueParams'] = params['trueParamsFuncUnits'][unitNr]

    print(params['labels'])
    print(params['biomkInFuncUnit'][unitNr])
    print(unitNr)
    labels = [params['labels'][b] for b in params['biomkInFuncUnit'][unitNr]]
    plotTrajParamsFuncUnit['labels'] = labels
    plotTrajParamsFuncUnit['colorsTraj'] =  [params['plotTrajParams']['colorsTrajBiomkB'][b]
                                             for b in params['biomkInFuncUnit'][unitNr]]

    print(params['unitNames'])
    print(unitNr)
    plotTrajParamsFuncUnit['title'] = params['unitNames'][unitNr]

    return plotTrajParamsFuncUnit

  @staticmethod
  def createPlotTrajParamsDis(params, disNr):

    plotTrajParamsDis = copy.deepcopy(params['plotTrajParams'])

    plotTrajParamsDis['diag'] = plotTrajParamsDis['diag'][params['binMaskSubjForEachDisD'][disNr]]

    if 'trueParamsDis' in params.keys():
      plotTrajParamsDis['trueParams'] = params['trueParamsDis'][disNr]


    # plotTrajParamsDis['labels'] = params['unitNames'] + [plotTrajParamsDis['labels'][i]
    #   for i in params['otherBiomkPerDisease'][disNr]]
    plotTrajParamsDis['labels'] = params['unitNames']
    plotTrajParamsDis['colorsTraj'] =  plotTrajParamsDis['colorsTrajUnitsU']
    # if False, plot estimated traj. in separate plot from true traj. If True, use only one plot
    plotTrajParamsDis['allTrajOverlap'] = False
    plotTrajParamsDis['title'] = params['disLabels'][disNr]


    return plotTrajParamsDis


  def plotTrajectories(self, res):
    pass
    # fig = self.plotterObj.plotTraj(self.gpModel)
    # fig.savefig('%s/allTrajFinal.png' % self.outFolder)

  def stageSubjects(self, indices):
    pass

  def stageSubjectsData(self, data):
    pass

  def plotTrajSummary(self, res):
    pass








