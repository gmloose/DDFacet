import numpy as np
from DDFacet.Imager.MSMF import ClassImageDeconvMachineMSMF
import copy
from DDFacet.ToolsDir.GiveEdges import GiveEdges
from DDFacet.ToolsDir.GiveEdges import GiveEdgesDissymetric
from DDFacet.Imager.ClassPSFServer import ClassPSFServer
from DDFacet.Imager.ModModelMachine import ClassModModelMachine
import multiprocessing
from DDFacet.Other import ClassTimeIt
from DDFacet.Other.progressbar import ProgressBar
import time
from DDFacet.Array import NpShared
from DDFacet.Other import MyLogger
log=MyLogger.getLogger("ClassInitSSDModel")
import traceback
from DDFacet.Other import ModColor
import time

class ClassInitSSDModelParallel():
    def __init__(self,GD,DicoVariablePSF,DicoDirty,RefFreq,MainCache=None,NCPU=1,IdSharedMem=""):
        self.DicoVariablePSF=DicoVariablePSF
        self.DicoDirty=DicoDirty
        GD=copy.deepcopy(GD)
        self.RefFreq=RefFreq
        self.MainCache=MainCache
        self.GD=GD
        self.NCPU=NCPU
        self.IdSharedMem=IdSharedMem
        print>>log,"Initialise HMP machine"
        self.InitMachine=ClassInitSSDModel(self.GD,
                                           self.DicoVariablePSF,
                                           self.DicoDirty,
                                           self.RefFreq,
                                           MainCache=self.MainCache,
                                           IdSharedMem=self.IdSharedMem)

    def setSSDModelImage(self,ModelImage):
        self.ModelImage=ModelImage

    def giveDicoInitIndiv(self,ListIslands,Parallel=True):
        NCPU=self.NCPU
        work_queue = multiprocessing.JoinableQueue()
        for iIsland in range(len(ListIslands)):
            work_queue.put({"iIsland":iIsland})
        result_queue=multiprocessing.JoinableQueue()
        NJobs=work_queue.qsize()
        workerlist=[]

        MyLogger.setSilent(["ClassImageDeconvMachineMSMF","ClassPSFServer","GiveModelMachine","ClassModelMachineMSMF"])
        
        print>>log,"Launch HMP workers"
        for ii in range(NCPU):
            W = WorkerInitMSMF(work_queue,
                               result_queue,
                               self.GD,
                               self.DicoVariablePSF,
                               self.DicoDirty,
                               self.RefFreq,
                               self.MainCache,
                               self.ModelImage,
                               ListIslands,
                               self.IdSharedMem)
            workerlist.append(W)
            if Parallel:
                workerlist[ii].start()

        timer = ClassTimeIt.ClassTimeIt()
        pBAR = ProgressBar('white', width=50, block='=', empty=' ', Title="  HMPing islands ", HeaderSize=10, TitleSize=13)
        #pBAR.disable()
        pBAR.render(0, '%4i/%i' % (0, NJobs))
        iResult = 0
        if not Parallel:
            for ii in range(NCPU):
                workerlist[ii].run()  # just run until all work is completed

        self.DicoInitIndiv={}
        while iResult < NJobs:
            DicoResult = None
            if result_queue.qsize() != 0:
                try:
                    DicoResult = result_queue.get()
                except:
                    pass

            if DicoResult == None:
                time.sleep(0.5)
                continue

            if DicoResult["Success"]:
                iResult+=1
                NDone=iResult
                intPercent=int(100*  NDone / float(NJobs))
                pBAR.render(intPercent, '%4i/%i' % (NDone,NJobs))

                iIsland=DicoResult["iIsland"]
                NameDico="%sDicoInitIsland_%5.5i"%(self.IdSharedMem,iIsland)
                Dico=NpShared.SharedToDico(NameDico)
                self.DicoInitIndiv[iIsland]=copy.deepcopy(Dico)
                NpShared.DelAll(NameDico)



        if Parallel:
            for ii in range(NCPU):
                workerlist[ii].shutdown()
                workerlist[ii].terminate()
                workerlist[ii].join()
        
        MyLogger.setLoud(["ClassImageDeconvMachineMSMF","ClassPSFServer","GiveModelMachine","ClassModelMachineMSMF"])
        return self.DicoInitIndiv

######################################################################################################

class ClassInitSSDModel():
    def __init__(self,GD,DicoVariablePSF,DicoDirty,RefFreq,MainCache=None,IdSharedMem=""):

        self.DicoVariablePSF=DicoVariablePSF
        self.DicoDirty=DicoDirty
        GD=copy.deepcopy(GD)
        self.RefFreq=RefFreq
        self.GD=GD
        self.GD["Parallel"]["NCPU"]=1
        self.GD["MultiFreqs"]["Alpha"]=[0,0,1]#-1.,1.,5]
        self.GD["MultiFreqs"]["Alpha"]=[-1.,1.,5]
        self.GD["ImagerDeconv"]["MinorCycleMode"]="MSMF"
        self.GD["ImagerDeconv"]["CycleFactor"]=0
        self.GD["ImagerDeconv"]["PeakFactor"]=0.01
        self.GD["ImagerDeconv"]["RMSFactor"]=0
        self.GD["ImagerDeconv"]["Gain"]=0.1

        self.GD["MultiScale"]["Scales"]=[0,1,2,4]
        self.GD["MultiScale"]["SolverMode"]="NNLS"
        #self.GD["MultiScale"]["SolverMode"]="PI"
        self.NFreqBands=len(DicoVariablePSF["freqs"])
        MinorCycleConfig=dict(self.GD["ImagerDeconv"])
        MinorCycleConfig["NCPU"]=self.GD["Parallel"]["NCPU"]
        MinorCycleConfig["NFreqBands"]=self.NFreqBands
        MinorCycleConfig["GD"] = self.GD
        #MinorCycleConfig["RefFreq"] = self.RefFreq

        ModConstructor = ClassModModelMachine(self.GD)
        ModelMachine = ModConstructor.GiveMM(Mode=self.GD["ImagerDeconv"]["MinorCycleMode"])
        ModelMachine.setRefFreq(self.RefFreq)
        MinorCycleConfig["ModelMachine"]=ModelMachine

        
        self.MinorCycleConfig=MinorCycleConfig
        self.DeconvMachine=ClassImageDeconvMachineMSMF.ClassImageDeconvMachine(MainCache=MainCache,CacheSharedMode=True,IdSharedMem=IdSharedMem,**self.MinorCycleConfig)
        self.Margin=100
        self.DicoDirty=DicoDirty
        self.Dirty=DicoDirty["ImagData"]
        self.MeanDirty=DicoDirty["MeanImage"]
        self.DeconvMachine.Init(PSFVar=self.DicoVariablePSF,PSFAve=self.DicoVariablePSF["PSFSideLobes"])
        self.DeconvMachine.Update(self.DicoDirty)
        self.DeconvMachine.updateRMS()

        #self.DicoBasicModelMachine=copy.deepcopy(self.DeconvMachine.ModelMachine.DicoSMStacked)

    def setSubDirty(self,ListPixParms):
        x,y=np.array(ListPixParms).T
        x0,x1=x.min(),x.max()+1
        y0,y1=y.min(),y.max()+1
        dx=x1-x0+self.Margin
        dy=y1-y0+self.Margin
        Size=np.max([dx,dy])
        if Size%2==0: Size+=1
        _,_,N0,_=self.Dirty.shape
        xc0,yc0=int(round(np.mean(x))),int(round(np.mean(y)))
        self.xy0=xc0,yc0
        N1=Size
        xc1=yc1=N1/2
        Aedge,Bedge=GiveEdges((xc0,yc0),N0,(xc1,yc1),N1)
        x0d,x1d,y0d,y1d=Aedge
        x0p,x1p,y0p,y1p=Bedge
        self.SubDirty=self.Dirty[:,:,x0d:x1d,y0d:y1d].copy()

        self.blc=(x0d,y0d)
        self.DeconvMachine.PSFServer.setBLC(self.blc)
        _,_,nx,ny=self.SubDirty.shape
        ArrayPixParms=np.array(ListPixParms)
        ArrayPixParms[:,0]-=x0d
        ArrayPixParms[:,1]-=y0d
        self.ArrayPixParms=ArrayPixParms
        self.DicoSubDirty={}
        for key in self.DicoDirty.keys():
            if key in ['ImagData', "MeanImage",'NormImage',"NormData"]:
                self.DicoSubDirty[key]=self.DicoDirty[key][...,x0d:x1d,y0d:y1d].copy()
            else:
                self.DicoSubDirty[key]=self.DicoDirty[key]

        # ModelImage=np.zeros_like(self.Dirty)
        # ModelImage[:,:,N0/2,N0/2]=10
        # ModelImage[:,:,N0/2+3,N0/2]=10
        # ModelImage[:,:,N0/2-2,N0/2-1]=10
        # self.setSSDModelImage(ModelImage)

        # Mask=np.zeros((nx,ny),np.bool8)
        # Mask[x,y]=1
        # self.SubMask=Mask


        x,y=ArrayPixParms.T
        Mask=np.zeros(self.DicoSubDirty['ImagData'].shape[-2::],np.bool8)
        Mask[x,y]=1
        self.SubMask=Mask


        if self.SSDModelImage is not None:
            self.SubSSDModelImage=self.SSDModelImage[:,:,x0d:x1d,y0d:y1d].copy()
            for ch in range(self.NFreqBands):
                self.SubSSDModelImage[ch,0][np.logical_not(self.SubMask)]=0
            self.addSubModelToSubDirty()


    def setSSDModelImage(self,ModelImage):
        self.SSDModelImage=ModelImage

    def addSubModelToSubDirty(self):
        ConvModel=np.zeros_like(self.SubSSDModelImage)
        nch,_,N0x,N0y=ConvModel.shape
        indx,indy=np.where(self.SubSSDModelImage[0,0]!=0)
        xc,yc=N0x/2,N0y/2
        self.DeconvMachine.PSFServer.setLocation(*self.xy0)
        PSF,MeanPSF=self.DeconvMachine.PSFServer.GivePSF()
        N1=PSF.shape[-1]
        for i,j in zip(indx.tolist(),indy.tolist()):
            ThisPSF=np.roll(np.roll(PSF,i-xc,axis=-2),j-yc,axis=-1)
            Aedge,Bedge=GiveEdgesDissymetric((xc,yc),(N0x,N0y),(N1/2,N1/2),(N1,N1))
            x0d,x1d,y0d,y1d=Aedge
            x0p,x1p,y0p,y1p=Bedge
            ConvModel[...,x0d:x1d,y0d:y1d]+=ThisPSF[...,x0p:x1p,y0p:y1p]*self.SubSSDModelImage[...,i,j].reshape((-1,1,1,1))

        MeanConvModel=np.mean(ConvModel,axis=0).reshape((1,1,N0x,N0y))
        self.DicoSubDirty['ImagData']+=ConvModel
        self.DicoSubDirty['MeanImage']+=MeanConvModel
        #print "MAX=",np.max(self.DicoSubDirty['MeanImage'])

        # import pylab
        # pylab.clf()
        # ax=pylab.subplot(1,3,1)
        # pylab.imshow(self.SubSSDModelImage[0,0],interpolation="nearest")
        # pylab.subplot(1,3,2,sharex=ax,sharey=ax)
        # pylab.imshow(PSF[0,0],interpolation="nearest")
        # pylab.subplot(1,3,3,sharex=ax,sharey=ax)
        # pylab.imshow(ConvModel[0,0],interpolation="nearest")
        # pylab.draw()
        # pylab.show(False)
        # pylab.pause(0.1)

            
    def giveModel(self,ListPixParms):
        T=ClassTimeIt.ClassTimeIt("giveModel")
        T.disable()
        self.setSubDirty(ListPixParms)
        T.timeit("setsub")
        ModConstructor = ClassModModelMachine(self.GD)
        ModelMachine = ModConstructor.GiveMM(Mode=self.GD["ImagerDeconv"]["MinorCycleMode"])
        print "ModelMachine"
        time.sleep(30)
        T.timeit("giveMM")
        self.ModelMachine=ModelMachine
        #self.ModelMachine.DicoSMStacked=self.DicoBasicModelMachine
        self.ModelMachine.setRefFreq(self.RefFreq,Force=True)
        self.MinorCycleConfig["ModelMachine"] = ModelMachine
        self.ModelMachine.setModelShape(self.SubDirty.shape)
        self.ModelMachine.setListComponants(self.DeconvMachine.ModelMachine.ListScales)
        T.timeit("setlistcomp")
        
        self.DeconvMachine.Update(self.DicoSubDirty)
        self.DeconvMachine.updateMask(np.logical_not(self.SubMask))
        self.DeconvMachine.updateModelMachine(ModelMachine)
        self.DeconvMachine.resetCounter()
        T.timeit("update")
        print "update"
        time.sleep(30)
        self.DeconvMachine.Deconvolve(UpdateRMS=False)
        T.timeit("deconv")
        print "deconv"
        time.sleep(30)

        ModelImage=self.ModelMachine.GiveModelImage()

        # import pylab
        # pylab.clf()
        # pylab.subplot(2,2,1)
        # pylab.imshow(self.DicoDirty["MeanImage"][0,0,:,:],interpolation="nearest")
        # pylab.colorbar()
        # pylab.subplot(2,2,2)
        # pylab.imshow(self.DicoSubDirty["MeanImage"][0,0,:,:],interpolation="nearest")
        # pylab.colorbar()
        # pylab.subplot(2,2,3)
        # pylab.imshow(self.SubMask,interpolation="nearest")
        # pylab.colorbar()
        # pylab.subplot(2,2,4)
        # pylab.imshow(ModelImage[0,0],interpolation="nearest")
        # pylab.colorbar()
        # pylab.draw()
        # pylab.show(False)
        # pylab.pause(0.1)


        x,y=self.ArrayPixParms.T
        SModel=ModelImage[0,0,x,y]
        AModel=self.ModelMachine.GiveSpectralIndexMap(DoConv=False,MaxDR=1e3)[0,0,x,y]
        return SModel,AModel



##########################################
####### Workers
##########################################
import os
import signal
           
class WorkerInitMSMF(multiprocessing.Process):
    def __init__(self,
                 work_queue,
                 result_queue,
                 GD,
                 DicoVariablePSF,
                 DicoDirty,
                 RefFreq,
                 MainCache,
                 ModelImage,
                 ListIsland,
                 IdSharedMem):
        multiprocessing.Process.__init__(self)
        self.work_queue = work_queue
        self.result_queue = result_queue
        self.kill_received = False
        self.exit = multiprocessing.Event()
        self.GD=GD
        self.DicoVariablePSF=DicoVariablePSF
        self.DicoDirty=DicoDirty
        self.RefFreq=RefFreq
        self.MainCache=MainCache
        self.ModelImage=ModelImage
        self.ListIsland=ListIsland
        self.InitMachine=None
        self.IdSharedMem=IdSharedMem

    def Init(self):
        self.InitMachine=ClassInitSSDModel(self.GD,
                                           self.DicoVariablePSF,
                                           self.DicoDirty,
                                           self.RefFreq,
                                           MainCache=self.MainCache,
                                           IdSharedMem=self.IdSharedMem)
        print "sleeeping init0"
        time.sleep(30)
        self.InitMachine.setSSDModelImage(self.ModelImage)
        print "sleeeping init1"
        time.sleep(30)

    def shutdown(self):
        self.exit.set()


    def initIsland(self, DicoJob):
        if self.InitMachine is None:
            self.Init()
        iIsland=DicoJob["iIsland"]
        Island=self.ListIsland[iIsland]
        SModel,AModel=self.InitMachine.giveModel(Island)
        

        DicoInitIndiv={"S":SModel,"Alpha":AModel}
        NameDico="%sDicoInitIsland_%5.5i"%(self.IdSharedMem,iIsland)
        NpShared.DicoToShared(NameDico, DicoInitIndiv)
        self.result_queue.put({"Success": True, "iIsland": iIsland})


    def run(self):
        while not self.kill_received and not self.work_queue.empty():
            DicoJob = self.work_queue.get()
            try:
                self.initIsland(DicoJob)
            except:
                print ModColor.Str("On island %i"%DicoJob["iIsland"])
                print traceback.format_exc()







