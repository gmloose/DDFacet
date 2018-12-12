import itertools

import numpy as np
from DDFacet.Other import MyLogger
from DDFacet.Other import ClassTimeIt
from DDFacet.Other import ModColor
log=MyLogger.getLogger("ClassModelMachineHogbom")
from DDFacet.Array import NpParallel
from DDFacet.Array import ModLinAlg
from DDFacet.ToolsDir import ModFFTW
from DDFacet.ToolsDir import ModToolBox
from DDFacet.Other import ClassTimeIt
from DDFacet.Other import MyPickle
from DDFacet.Other import reformat

from DDFacet.ToolsDir.GiveEdges import GiveEdges
from DDFacet.Imager import ClassModelMachine as ClassModelMachinebase
from DDFacet.Imager import ClassFrequencyMachine
import scipy.ndimage
from SkyModel.Sky import ModRegFile
from pyrap.images import image
from SkyModel.Sky import ClassSM
import os

class ClassModelMachine(ClassModelMachinebase.ClassModelMachine):
    def __init__(self,*args,**kwargs):
        ClassModelMachinebase.ClassModelMachine.__init__(self, *args, **kwargs)
        self.DicoSMStacked={}
        self.DicoSMStacked["Type"]="Hogbom"

    def setRefFreq(self, RefFreq, Force=False):
        if self.RefFreq is not None and not Force:
            print>>log, ModColor.Str("Reference frequency already set to %f MHz" % (self.RefFreq/1e6))
            return

        self.RefFreq = RefFreq
        self.DicoSMStacked["RefFreq"] = RefFreq

    def setFreqMachine(self,GridFreqs, DegridFreqs):
        # Initiaise the Frequency Machine
        self.DegridFreqs = DegridFreqs
        self.GridFreqs = GridFreqs
        self.FreqMachine = ClassFrequencyMachine.ClassFrequencyMachine(GridFreqs, DegridFreqs, self.DicoSMStacked["RefFreq"], self.GD)
        self.FreqMachine.set_Method(mode=self.GD["Hogbom"]["FreqMode"])

    def ToFile(self, FileName, DicoIn=None):
        print>> log, "Saving dico model to %s" % FileName
        if DicoIn is None:
            D = self.DicoSMStacked
        else:
            D = DicoIn

        D["GD"] = self.GD
        D["Type"] = "Hogbom"
        D["ListScales"] = "Delta"
        D["ModelShape"] = self.ModelShape
        MyPickle.Save(D, FileName)

    def FromFile(self, FileName):
        print>> log, "Reading dico model from %s" % FileName
        self.DicoSMStacked = MyPickle.Load(FileName)
        self.FromDico(self.DicoSMStacked)

    def FromDico(self, DicoSMStacked):
        self.DicoSMStacked = DicoSMStacked
        self.RefFreq = self.DicoSMStacked["RefFreq"]
        self.ListScales = self.DicoSMStacked["ListScales"]
        self.ModelShape = self.DicoSMStacked["ModelShape"]

    def setModelShape(self, ModelShape):
        self.ModelShape = ModelShape

    def AppendComponentToDictStacked(self, key, Fpol, Sols, pol_array_index=0):
        """
        Adds component to model dictionary (with key l,m location tupple). Each
        component may contain #basis_functions worth of solutions. Note that
        each basis solution will have multiple Stokes components associated to it.
        Args:
            key: the (l,m) centre of the component
            Fpol: Weight of the solution
            Sols: Nd array of solutions with length equal to the number of basis functions representing the component.
            pol_array_index: Index of the polarization (assumed 0 <= pol_array_index < number of Stokes terms in the model)
        Post conditions:
        Added component list to dictionary (with keys (l,m) coordinates). This dictionary is stored in
        self.DicoSMStacked["Comp"] and has keys:
            "SolsArray": solutions ndArray with shape [#basis_functions,#stokes_terms]
            "SumWeights": weights ndArray with shape [#stokes_terms]
        """
        nchan, npol, nx, ny = self.ModelShape
        if not (pol_array_index >= 0 and pol_array_index < npol):
            raise ValueError("Pol_array_index must specify the index of the slice in the "
                             "model cube the solution should be stored at. Please report this bug.")

        DicoComp = self.DicoSMStacked.setdefault("Comp", {})

        if not (key in DicoComp.keys()):
            DicoComp[key] = {}
            for p in range(npol):
                DicoComp[key]["SolsArray"] = np.zeros((Sols.size, npol), np.float32)
                DicoComp[key]["SumWeights"] = np.zeros((npol), np.float32)

        Weight = 1.
        Gain = self.GainMachine.GiveGain()

        #tmp = Sols.ravel()
        SolNorm = Sols.ravel() * Gain * np.mean(Fpol)

        DicoComp[key]["SumWeights"][pol_array_index] += Weight
        DicoComp[key]["SolsArray"][:, pol_array_index] += Weight * SolNorm

    def GiveModelList(self, FreqIn=None, DoAbs=False, threshold=0.1):
        """
        Iterates through components in the "Comp" dictionary of DicoSMStacked,
        returning a list of model sources in tuples looking like
        (model_type, coord, flux, ref_freq, alpha, model_params).

        model_type is obtained from self.ListScales
        coord is obtained from the keys of "Comp"
        flux is obtained from the entries in Comp["SolsArray"]
        ref_freq is obtained from DicoSMStacked["RefFreq"]
        alpha is obtained from self.ListScales
        model_params is obtained from self.ListScales

        If multiple scales exist, multiple sources will be created
        at the same position, but different fluxes, alphas etc.

        """
        if DoAbs:
            f_apply = np.abs
        else:
            f_apply = lambda x: x
            
        DicoComp = self.DicoSMStacked["Comp"]
        ref_freq = self.DicoSMStacked["RefFreq"]
        
        if FreqIn is None:
           FreqIn=np.array([ref_freq], dtype=np.float32)
            
        # Construct alpha map
        IM = self.GiveModelImage(self.FreqMachine.Freqsp)
        nchan, npol, Nx, Ny = IM.shape
        # Fit the alpha map
        self.FreqMachine.FitAlphaMap(IM[:, 0, :, :],
                                     threshold=1.0e-6)  # should set threshold based on SNR of final residual
        alpha = self.FreqMachine.weighted_alpha_map.reshape((1, 1, Nx, Ny))

        # Assumptions:
        # DicoSMStacked is a dictionary of "Solution" dictionaries
        # keyed on (l, m), corresponding to some point  source. 
        # Components associated with the source for each scale are
        # located in self.ListScales.

        def _model_map(coord, component):
            """
            Given a coordinate and component obtained from DicoMap
            returns a tuple with the following information
            (ModelType, coordinate, vector of STOKES solutions per basis function, alpha, shape data)
            """
            sa = component["SolsArray"]
            return [("Delta",                         # type
                     coord,                           # coordinate
                     f_apply(self.FreqMachine.Eval_Degrid(sa,
                                                          FreqIn)), # only a solution for I
                     ref_freq,                        # reference frequency
                     alpha[0, 0, coord[0], coord[1]], # alpha estimate
                     None)]                           # shape

        # Lazily iterate through DicoComp entries and associated ListScales and SolsArrays,
        # assigning values to arrays
        source_iter = itertools.chain.from_iterable(_model_map(coord, comp)
            for coord, comp in DicoComp.iteritems())

        # Create list with iterator results
        return [s for s in source_iter]


    def GiveModelImage(self, FreqIn=None, DoAbs=False, out=None):
        if DoAbs:
            f_apply = np.abs
        else:
            f_apply = lambda x: x

        RefFreq=self.DicoSMStacked["RefFreq"]
        # Default to reference frequency if no input given
        if FreqIn is None:
            FreqIn=np.array([RefFreq], dtype=np.float32)

        FreqIn = np.array([FreqIn.ravel()], dtype=np.float32).flatten()

        DicoComp = self.DicoSMStacked.setdefault("Comp", {})
        _, npol, nx, ny = self.ModelShape

        # The model shape has nchan=len(GridFreqs)
        nchan = FreqIn.size
        if out is not None:
            if out.shape != (nchan,npol,nx,ny) or out.dtype != np.float32:
                raise RuntimeError("supplied image has incorrect type (%s) or shape (%s)" % (out.dtype, out.shape))
            ModelImage = out
        else:
            ModelImage = np.zeros((nchan,npol,nx,ny),dtype=np.float32)
        DicoSM = {}
        for key in DicoComp.keys():
            for pol in range(npol):
                Sol = DicoComp[key]["SolsArray"][:, pol]  # /self.DicoSMStacked[key]["SumWeights"]
                x, y = key
                #tmp = self.FreqMachine.Eval_Degrid(Sol, FreqIn)
                interp = self.FreqMachine.Eval_Degrid(Sol, FreqIn)
                if interp is None:
                    raise RuntimeError("Could not interpolate model onto degridding bands. Inspect your data, check 'Hogbom-PolyFitOrder' or "
                                       "if you think this is a bug report it.")
                else:
                    ModelImage[:, pol, x, y] += f_apply(interp)

        return ModelImage

    def GiveSpectralIndexMap(self, threshold=0.1, save_dict=True):
        # Get the model image
        IM = self.GiveModelImage(self.FreqMachine.Freqsp)
        nchan, npol, Nx, Ny = IM.shape

        try:
            # Fit the alpha map
            self.FreqMachine.FitAlphaMap(IM,
                                         threshold=threshold)  # should set threshold based on SNR of final residual

            if save_dict:
                FileName = self.GD['Output']['Name'] + ".Dicoalpha"
                print>> log, "Saving componentwise SPI map to %s" % FileName

                MyPickle.Save(self.FreqMachine.alpha_dict, FileName)

            return self.FreqMachine.weighted_alpha_map.reshape((1, 1, Nx, Ny))
        except:
            return np.zeros((1, 1, Nx, Ny))

    def PutBackSubsComps(self):
        # if self.GD["Data"]["RestoreDico"] is None: return

        SolsFile = self.GD["DDESolutions"]["DDSols"]
        if not (".npz" in SolsFile):
            Method = SolsFile
            ThisMSName = reformat.reformat(os.path.abspath(self.GD["Data"]["MS"]), LastSlash=False)
            SolsFile = "%s/killMS.%s.sols.npz" % (ThisMSName, Method)
        DicoSolsFile = np.load(SolsFile)
        SourceCat = DicoSolsFile["SourceCatSub"]
        SourceCat = SourceCat.view(np.recarray)
        # RestoreDico=self.GD["Data"]["RestoreDico"]
        RestoreDico = DicoSolsFile["ModelName"][()][0:-4] + ".DicoModel"

        print>> log, "Adding previously subtracted components"
        ModelMachine0 = ClassModelMachine(self.GD)

        ModelMachine0.FromFile(RestoreDico)

        _, _, nx0, ny0 = ModelMachine0.DicoSMStacked["ModelShape"]

        _, _, nx1, ny1 = self.ModelShape
        dx = nx1 - nx0

        for iSource in range(SourceCat.shape[0]):
            x0 = SourceCat.X[iSource]
            y0 = SourceCat.Y[iSource]

            x1 = x0 + dx
            y1 = y0 + dx

            if not ((x1, y1) in self.DicoSMStacked["Comp"].keys()):
                self.DicoSMStacked["Comp"][(x1, y1)] = ModelMachine0.DicoSMStacked["Comp"][(x0, y0)]
            else:
                self.DicoSMStacked["Comp"][(x1, y1)] += ModelMachine0.DicoSMStacked["Comp"][(x0, y0)]
