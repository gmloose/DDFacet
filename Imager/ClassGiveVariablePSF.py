import numpy as np
import pylab

class ClassVariablePSF():
	def __init__ (self, phasePSF=None, freq0=None, dtime=None, dfreq=None, cellsize=None, ):
		"""
		   the class Evaluate the PSF at l,m given the PSF at the phase center
		""";
		# the phase center PSF
		self.phasePSF = phasePSF;
		# Observed frequency
		self.freq0 = freq0 or 1.;
		# the compression in time
		self.dtime = dtime or 0;
		# the compression in frequency
		self.dfreq = dfreq or 0;
		# the resolution or the pixel size in radian
		self.resolution = np.pi*(cellsize/3600.)/180.;
	

	def givePSF(self, lcor=None, mcor=None):
		"""
		   evaluate the pseudo PSF given lcor and mcor in pixel
		   a pseudeo PSF is F(lcor,mcor) o phasePSF, where o is convolution
		   the idea here is to find F(lcor,mcor) giving phasePSF and lcor, mcor
		""";
		
		n, _ = self.phasePSF.shape
		lcor = (lcor-n/2)*self.resolution*np.pi/(180*3600.)
		mcor = (mcor-n/2)*self.resolution*np.pi/(180*3600.)
		#lcor, mcor = (lcor*np.pi/180., mcor*np.pi/180.)
		print "******** xxx start generating pseudo PSF at cordinates number pixel %d (%f, %f) radian"%(n, lcor,mcor)
		
		# total Field of view and uv-cellsize size
		Fov = n*self.resolution
		Delta_u, Delta_v = (1/Fov, 1/Fov)
		u = np.linspace(-(n-1)/2*Delta_u,(n-1)/2*Delta_u,n)
		v = np.linspace(-(n-1)/2*Delta_v,(n-1)/2*Delta_v,n)
		uu,vv = np.meshgrid(u,v)
		# angle of orientation
		angle = np.arctan(uu/vv)
		angle[uu==0]=1e-9
		# uv distance in radian
		uvd = np.sqrt(uu**2 + vv**2)
		# angular velocity on one year
		ang_velocity = 2*np.pi/(3600.*24.)
		du =ang_velocity*uvd*(-1*np.sin(angle))
		dv =ang_velocity*uvd*np.cos(angle)
		varietion_time = np.pi*(du*lcor+dv*mcor)*self.dtime
		varietion_freq = np.pi*((uvd/(self.freq0))*self.dfreq*lcor + (uvd/(self.freq0))*self.dfreq*mcor) 
		# smearing in time
		smearing_time = np.sin(varietion_time)/(varietion_time)
		smearing_time[varietion_time==0] = 1.
		smearing_freq = np.sin(varietion_freq)/(varietion_freq)
		smearing_freq[varietion_freq==0] = 1.
		#print "",smearing_freq
		UVdomain = np.fft.fftshift(np.fft.fft2(self.phasePSF))
		smearPsfUVdomain = smearing_time*smearing_freq*UVdomain
		smearPSF = np.fft.ifft2(np.fft.ifftshift(smearPsfUVdomain))
		print "******** xxx end pseudo PSF generate at cordinates (%f, %f) radian"%(lcor,mcor)
		#pylab.imshow(smearPSF.real)
		#pylab.show()
		return smearPSF.real;
	


if __name__ == "__main__":
	from pyrap.images import image
	import argparse
	
	parser = argparse.ArgumentParser()
	parser.add_argument('--psf', help='psf in fits file')
	parser.add_argument('--freq', help='Observed frequency')
	parser.add_argument('--dtime', help='compression time')
	parser.add_argument('--dfreq', help='compression frequnecy')
	parser.add_argument('--cellsize', help='psf in fits filecellsize')
	parser.add_argument('--ldirection', help='source l coordinate in degree')
	parser.add_argument('--mdirection', help='source m coordinate in degree')
	args = vars(parser.parse_args())
	psf, freq0, dtime, dfreq, cellsize, ldirection, mdirection = (args['psf'], args['freq'], args['dtime'], args['dfreq'],args['cellsize'],
								    args['ldirection'], args['mdirection'])
	
	if freq0 != None:
		freq0 = float(freq0)
	if dtime != None:
		dtime = int(dtime)
	if dfreq != None:
		dfreq = int(dfreq)
	if cellsize != None:
		cellsize = float(cellsize)
	if ldirection != None:
		ldirection = float(ldirection)
	if mdirection != None:
		mdirection = float(mdirection)
	   
	imagepsf = image(psf)
	psf = imagepsf.getdata()
	classpsf = ClassVariablePSF(phasePSF=psf.real[0,0,...], freq0=freq0, dtime=dtime, dfreq=dfreq, cellsize=cellsize)
	psflm = classpsf.givePSF(ldirection, mdirection)
	pylab.imshow(psflm)
	pylab.show()
