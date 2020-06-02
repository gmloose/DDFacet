# '''
# DDFacet, a facet-based radio imaging package
# Copyright (C) 2013-2016  Cyril Tasse, l'Observatoire de Paris,
# SKA South Africa, Rhodes University
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.
# '''
#
# from __future__ import absolute_import
# from __future__ import division
# from __future__ import print_function

# from DDFacet.compatibility import range
# import unittest
#
# import DDFacet.Tests.ShortAcceptanceTests.ClassCompareFITSImage
#
#
# class TestSSDKillMS(DDFacet.Tests.ShortAcceptanceTests.ClassCompareFITSImage.ClassCompareFITSImage):
#     @classmethod
#     def defineImageList(cls):
#         """ Method to define set of reference images to be tested.
#             Can be overridden to add additional output products to the test.
#             These must correspond to whatever is used in writing out the FITS files (eg. those in ClassDeconvMachine.py)
#             Returns:
#                 List of image identifiers to reference and output products
#         """
#         return ['dirty', 'dirty.corr', 'psf', 'NormFacets', 'Norm',
#                 'app.residual', 'app.model',
#                 'app.convmodel', 'app.restored']
#
#     @classmethod
#     def defineMaxSquaredError(cls):
#         """ Method defining maximum error tolerance between any pair of corresponding
#             pixels in the output and corresponding reference FITS images.
#             Should be overridden if another tolerance is desired
#             Returns:
#                 constant for maximum tolerance used in test case setup
#         """
#         return [1e-6,1e-6,1e-6,1e-4,1e-4,
#                 5e-1,5e-1,
#                 5e-1,5e-1]
#
#     @classmethod
#     def defMeanSquaredErrorLevel(cls):
#         """ Method defining maximum tolerance for the mean squared error between any
#             pair of FITS images. Should be overridden if another tolerance is
#             desired
#             Returns:
#             constant for tolerance on mean squared error
#         """
#         return [1e-7,1e-7,1e-7,1e-7,1e-7,
#                 1e-5,1e-5,
#                 1e-5,1e-5]
#
#     @classmethod
#     def timeoutsecs(cls):
#         return 21600 * 4
#
# if __name__ == '__main__':
#     unittest.main()
