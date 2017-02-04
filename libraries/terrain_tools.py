#Import all the functions from the fortran library
import numpy as np
import terrain_tools_fortran as ttf
import sklearn.cluster

def compute_basin_delineation_nbasins(dem,mask,res,nbasins):

 channel_threshold = 10**6
 #Calculate the d8 accumulation area and flow direction
 (area,fdir) = ttf.calculate_d8_acc(dem,res)
 area[mask == 0] = 0.0
 #Iterate until the number of basins match the desired (bisection)
 max_threshold = np.max(area) - res**2
 min_threshold = max_threshold/1000
 #Calculate number of basins for the two boundaries
 channels = ttf.calculate_channels(area,channel_threshold,max_threshold,fdir)
 min_basins = ttf.delineate_basins(channels,mask,fdir)
 min_nbasins = np.unique(min_basins)[1::].size
 print min_nbasins
 #Min iteration
 channels = ttf.calculate_channels(area,channel_threshold,min_threshold,fdir)
 max_basins = ttf.delineate_basins(channels,mask,fdir)
 max_nbasins = np.unique(max_basins)[1::].size
 for i in xrange(10):
  #Calculate midpoint
  c = (np.log(max_threshold) + np.log(min_threshold))/2
  #Calculate the number of basins for the given threshold
  channels = ttf.calculate_channels(area,channel_threshold,np.exp(c),fdir)
  basins = ttf.delineate_basins(channels,mask,fdir)
  c_nbasins = np.unique(basins)[1::].size
  print min_nbasins,c_nbasins,max_nbasins
  #Determine if we have found our solution
  if c_nbasins == nbasins:
   return basins
  #Create the new boundaries
  if nbasins < c_nbasins:
   min_threshold = np.exp(c)
   channels = ttf.calculate_channels(area,channel_threshold,min_threshold,fdir)
   max_basins = ttf.delineate_basins(channels,mask,fdir)
   max_nbasins = np.unique(max_basins)[1::].size
  else:
   max_threshold = np.exp(c)
   channels = ttf.calculate_channels(area,channel_threshold,max_threshold,fdir)
   min_basins = ttf.delineate_basins(channels,mask,fdir)
   min_nbasins = np.unique(min_basins)[1::].size

 print "Did not converge. Returning the best"
 return basins

def define_hrus(basins,dem,channels):

 nbins = 10
 #Define the unique basins
 ubasins = np.unique(basins)[1::]
 tmp = np.copy(basins)
 tmp[:] = 0
 #Create the dem bins
 for basin in ubasins:
  smask = basins == basin
  #Bin the elevation data
  (hist,bins) = np.histogram(dem[smask],bins=nbins)
  #Place the data
  for ibin in xrange(nbins):
   smask = (basins == basin) & (dem >= bins[ibin]) & (dem < bins[ibin+1])
   tmp[smask] = np.mean(dem[smask])
 import matplotlib.pyplot as plt
 tmp = np.ma.masked_array(tmp,tmp==0)
 plt.imshow(tmp)
 plt.show()

 return 

def calculate_basin_properties(basins,res,latitude,longitude,fdir):

 nb = np.max(basins)
 (ah,lath,lonh,hid,nid) = ttf.calculate_basin_properties(basins,res,nb,fdir,
                               latitude,longitude)
 properties = {
               'area':ah,
               'latitude':lath,
               'longitude':lonh,
               'id':hid,
               'nid':nid
              }

 return properties

def reduce_basin_number(basins,bp,nbasins_goal):

 ids = bp['id']-1
 nids = bp['nid']-1
 area = bp['area']
 nbasins = ids.size

 while nbasins > nbasins_goal:
  #Determine the basin to add
  #To attempt similar area we will first determine which one decreases the area standard deviation
  astd = []
  #Get the smallest 10
  ibs = np.argsort(area)[0:10]
  
  for ib in ibs:
   area_cp = np.copy(area)
   #tmp = np.argmin(area[nids>=0])
   #ib = np.where(area_cp == area_cp[nids>=0][tmp])[0][0]
   area_cp[ids==nids[ib]] = area_cp[ids==nids[ib]] + area_cp[ib]
   astd.append(np.std(area_cp))
  astd = np.array(astd)
  tmp = np.argmin(astd[nids[ibs]>=0])
  ib = ibs[np.where(astd == astd[nids[ibs]>=0][tmp])[0][0]]
 
  #Add it to its next basin
  area[ids==nids[ib]] = area[ids==nids[ib]] + area[ib]
  #Wherever the original basin id was the next basin replace it
  nids[nids == ids[ib]] = nids[ib]
  #Set the basin map to new id
  basins[basins == ids[ib]+1] = nids[ib]+1
  #Remove the row of the basin
  ids = np.delete(ids,ib)
  nids = np.delete(nids,ib)
  area = np.delete(area,ib)
  #Update the number of basins
  nbasins = nbasins - 1

 #Reassign basins
 ubasins = np.unique(basins)[1::]
 for i in xrange(ubasins.size):
  basins[basins == ubasins[i]] = i+1
 
 #Reset the undefined values
 basins[basins <= 0] = -9999

 return basins

def calculate_hillslope_properties(hillslopes,dem,basins,res,latitude,
    longitude,depth2channel,slope,aspect,cplan,cprof,channels):

 nh = np.max(hillslopes)+1
 (eh,ah,bh,lath,lonh,erange,hid,d2c,slope,haspect,hcplan,hcprof,hmaxd2c,hmind2c,htwidth,hbwidth) = ttf.calculate_hillslope_properties(hillslopes,dem,basins,res,nh,latitude,longitude,depth2channel,slope,aspect,cplan,cprof,channels)
 properties = {'elevation':eh,
               'area':ah,
               'basin':bh,
               'latitude':lath,
               'longitude':lonh,
               'range':erange,
               'id':hid,
	       'd2c':d2c,
	       'slope':slope,
               #'c2n':hc2n,
               #'g2t':hg2t,
               #'maxsmc':hmaxsmc,
               'aspect':haspect,
               'cplan':hcplan,
               'cprof':hcprof,
               'mind2c':hmind2c,
               'maxd2c':hmaxd2c,
               'twidth':htwidth,
               'bwidth':hbwidth,
              }

 #Remove nans
 m = np.isnan(eh) == 0
 for p in properties:
  properties[p] = properties[p][m]

 #Compute the hillslope lengths (the 30 accounts for the beginning and end)
 a = properties['maxd2c'] - properties['mind2c']
 b = a/properties['slope'] + res
 properties['length'] = b
 #properties['length'] = (a**2 + b**2)**0.5

 #Compute the ratio of width top to bottom
 properties['twidth'][properties['twidth'] == 0] = 1
 properties['bwidth'][properties['bwidth'] == 0] = 1
 properties['twidth'] = res*properties['twidth']
 properties['bwidth'] = res*properties['bwidth']
 r = properties['twidth']/properties['bwidth']
 #Restrict to 10/1
 m = r > 10
 r[m] = 10
 properties['twidth'][m] = 10*properties['bwidth'][m]
 properties['rwidth'] = r

 return properties

def create_tiles_kmeans(basins,covariates,ntiles):

 #Define the mask
 mask = basins > 0
 
 #Initialize the cluster number
 icluster = 0

 #Initialize the hru map
 hrus = np.empty(covariates[covariates.keys()[0]]['data'].shape).astype(np.int32)
 hrus[:] = -9999

 #Iterate through each hillslope making the hrus
 ub = np.unique(basins)[1::]
 for ib in ub:
  mask = basins == ib

  #Define the data and the bins
  X = []
  for var in covariates:
   X.append(covariates[var]['data'][mask])
  X = np.array(X).T

  #Normalize the data
  for i in xrange(X.shape[1]):
   X[:,i] = (X[:,i]-np.min(X[:,i]))/(np.max(X[:,i])-np.min(X[:,i]))
   
  #Subsample the array
  np.random.seed(1)
  minsamples = 10**5
  if X.shape[0] > minsamples:
   Xf = X[np.random.choice(np.arange(X.shape[0]),minsamples),:]
  else:
   Xf = X

  #Cluster the data
  init = 0.5*np.ones((ntiles,Xf.shape[1]))
  batch_size = 25*ntiles
  init_size = 3*batch_size
  clf = sklearn.cluster.MiniBatchKMeans(ntiles,random_state=1,init=init,batch_size=batch_size,init_size=init_size)
  #clf = sklearn.cluster.KMeans(ntiles,random_state=1)
  clf.fit(Xf)#
  clf_output = clf.predict(X)

  #Map the hrus
  hrus[mask] = clf_output+icluster
 
  #Update icluster
  icluster = np.max(hrus)+1

 #Clean up the hrus
 uhrus = np.unique(hrus)[1::]
 hrus_new = np.copy(hrus)
 for i in xrange(uhrus.size):
  hrus_new[hrus == uhrus[i]] = i
 hrus = hrus_new

 #Finalize hrus array
 hrus[hrus < 0] = -9999

 return hrus

def create_nd_histogram(hillslopes,covariates):

 undef = -9999.0
 #Construct the mask
 m = hillslopes != undef
 for var in covariates:
  m = m & (covariates[var]['data'] != -9999.0)
 
 #Initialize the cluster number
 icluster = -1

 #Initialize the hru map
 hrus = np.empty(covariates[covariates.keys()[0]]['data'].shape).astype(np.float32)
 hrus[:] = -9999

 #Iterate through each hillslope making the hrus
 uh = np.unique(hillslopes)
 uh = uh[uh != -9999]
 for ih in uh:
  mask = (hillslopes == ih) & m

  #Define the data and the bins
  bins,data = [],[]
  for var in covariates:
   bins.append(covariates[var]['nbins'])
   #Convert the data to percentiles if necessary
   if covariates[var]['type'] == 'p':
    tmp = np.copy(covariates[var]['data'][mask])
    argsort = np.argsort(tmp)
    tmp[argsort] = np.linspace(0,1,tmp.size)
    #Have this data replace the covariate information 
    covariates[var]['data'][mask] = tmp
   else:
    tmp = np.copy(covariates[var]['data'][mask])
   data.append(tmp)
   #data.append(covariates[var]['data'][mask])
  bins = np.array(bins)
  data = np.array(data).T

  #Create the histogram
  H,edges = np.histogramdd(data,bins=bins)
  H = H/np.sum(H) 

  #Create a dictionary of hru info
  clusters = {}
  Hfl = H.flat
  for i in xrange(H.size):
   coords = Hfl.coords
   if H[coords] > 0:
    icluster = icluster + 1
    clusters[icluster] = {'pct':H[coords]}
    clusters[icluster]['bounds'] = {}
    for var in covariates:
     key = covariates.keys().index(var)
     clusters[icluster]['bounds'][var] = [edges[key][coords[key]],edges[key][coords[key]+1]]
   Hfl.next()

  #Map the hru id to the grid
  for cid in clusters.keys():
   for id in covariates.keys():
    if covariates.keys().index(id) == 0: string = "(covariates['%s']['data'] >= clusters[%d]['bounds']['%s'][0]) & (covariates['%s']['data'] <= clusters[%d]['bounds']['%s'][1]) & mask" % (id,cid,id,id,cid,id)
    else: string = string +  " & (covariates['%s']['data'] >= clusters[%d]['bounds']['%s'][0]) & (covariates['%s']['data'] <= clusters[%d]['bounds']['%s'][1]) & mask" % (id,cid,id,id,cid,id)
   idx = eval('np.where(%s)' % string)
   hrus[idx] = cid + 1

 #Cleanup the hrus
 hrus = np.array(hrus,order='f').astype(np.int32)
 ttf.cleanup_hillslopes(hrus)
 hrus[hrus >= 0] = hrus[hrus >= 0] + 1

 return hrus

def create_hillslope_tiles(hillslopes,depth2channel,nbins,bins):

 undef = -9999.0
 #Construct the mask
 m = (hillslopes != undef) & (depth2channel != undef)

 #Define the clusters for each hillslope
 clusters = np.copy(hillslopes)
 uh = np.unique(hillslopes)
 uh = uh[uh != undef]
 for ih in uh:
  mask = (hillslopes == ih) & m
  tmp = np.copy(depth2channel[mask])
  argsort = np.argsort(tmp)
  tmp[argsort] = np.linspace(0,1,tmp.size)
  depth2channel[mask] = tmp
  (hist,bins) = np.histogram(tmp,bins=nbins[ih-1])
  for ibin in xrange(nbins[ih-1]):
   #if ibin == 0:smask = mask & (depth2channel >= np.min(tmp)) & (depth2channel <= bins[ih-1][ibin+1])
   #elif ibin == nbins[ih-1]-1:smask = mask & (depth2channel >= bins[ih-1][ibin]) & (depth2channel <= np.max(tmp))
   #else: smask = mask & (depth2channel >= bins[ih-1][ibin]) & (depth2channel <= bins[ih-1][ibin+1])
   smask = mask & (depth2channel >= bins[ibin]) & (depth2channel <= bins[ibin+1])
   clusters[smask] = ibin+1

 #Cleanup the tiles
 clusters = np.array(clusters,order='f').astype(np.int32)
 ttf.cleanup_hillslopes(clusters)
 clusters[clusters >= 0] = clusters[clusters >= 0] + 1

 return clusters

def create_hrus(hillslopes,htiles,covariates,nclusters):

 import sklearn.cluster
 hrus = np.copy(hillslopes)
 hrus[:] = -9999
 #Iterate through each hillslope and tile and compute hrus
 uhs = np.unique(hillslopes)
 uhs = uhs[uhs != -9999]
 maxc = 1
 for uh in uhs:
  mh = hillslopes == uh
  uts = np.unique(htiles[mh])
  for ut in uts:
   mt = mh & (htiles == ut)
   #prepare the covariate data
   X = []
   for var in covariates:
    tmp = covariates[var][mt]
    tmp[(np.isnan(tmp) == 1) | (np.isinf(tmp) == 1)] = 0.0
    #Convert to percentiles
    argsort = np.argsort(tmp)
    tmp[argsort] = np.linspace(0,1,tmp.size)
    X.append(tmp)
   #cluster the data
   X = np.array(X).T
   state = 35799
   model = sklearn.cluster.KMeans(n_clusters=nclusters,random_state=state)
   clusters = model.fit_predict(X)+maxc
   hrus[mt] = clusters
   maxc = np.max(clusters)+1

 return hrus

def calculate_hru_properties(hillslopes,tiles,channels,res,nhillslopes,hrus,depth2channel,slope,basins):

 tmp = np.unique(hrus)
 tmp = tmp[tmp != -9999]
 nhru = tmp.size
 (wb,wt,l,hru_position,hid,tid,hru,hru_area,hru_dem,hru_slope) = ttf.calculate_hru_properties(hillslopes,tiles,channels,basins,nhru,res,nhillslopes,hrus,depth2channel,slope)
 hru_properties = {'width_bottom':wb,
                   'width_top':wt,
                   'hillslope_length':l,
                   'hillslope_position':hru_position,
                   'hillslope_id':hid,
                   'tile_id':tid,
                   'hru':hru,
                   'area':hru_area,
                   'slope':hru_slope,
                   'depth2channel':hru_dem}

 return hru_properties
                       
#def cluster_hillslopes(hp,hillslopes,nclusters,covariates):
def cluster_hillslopes(hillslopes,nclusters,covariates,hp_in):

 import sklearn.cluster
 X = []
 for var in covariates:
  tmp = covariates[var]
  tmp[(np.isnan(tmp) == 1) | (np.isinf(tmp) == 1)] = 0.0
  X.append(tmp)
 X = np.array(X).T
 state = 35799#80098
 model = sklearn.cluster.KMeans(n_clusters=nclusters,random_state=state)
 clusters = model.fit_predict(X)+1
 #Clean up the hillslopes
 hillslopes = np.array(hillslopes,order='f').astype(np.int32)
 ttf.cleanup_hillslopes(hillslopes)
 #Assign the new ids to each hillslpe
 hillslopes_clusters = ttf.assign_clusters_to_hillslopes(hillslopes,clusters)
 #Determine the number of hillslopes per cluster
 uclusters = np.unique(clusters)
 nhillslopes = []
 for cluster in uclusters:
  nhillslopes.append(np.sum(clusters == cluster))
 nhillslopes = np.array(nhillslopes)

 #Compute the average value for each cluster of each property
 hp_out = {}
 hp_out['hid'] = []
 for cluster in uclusters:
  hp_out['hid'].append(cluster)
  m = clusters == cluster
  for var in hp_in:
   if var not in hp_out:hp_out[var] = []
   hp_out[var].append(np.mean(hp_in[var][m]))
 for var in hp_out:
  hp_out[var] = np.array(hp_out[var])
 
 return (hillslopes_clusters,nhillslopes,hp_out)

def curate_hru_properties(hru_properties,hp):

 #Iterate per hillslope
 for hid in hp['hid']:
  m = hru_properties['hillslope_id'] == hid
  #redo the length
  (d2c,idx) = np.unique(hru_properties['depth2channel'][m],return_inverse=True)
  #Calculate the update properties
  hlength = hp['length'][hid-1]/d2c.size*np.ones(d2c.size)
  hpos = np.cumsum(hlength) - hlength[0]/2
  helev = hp['slope'][hid-1]*hpos
  slope = hp['slope'][hid-1]/d2c.size*np.ones(d2c.size)
  width = np.linspace(1,hp['rwidth'][hid-1],d2c.size+1)
  twidth = width[1:]
  bwidth = width[0:-1]
  #Iterate through elevation layer to adjust the widths
  otwidth = hru_properties['width_top'][m]
  ntwidth = twidth[idx]
  nbwidth = bwidth[idx]
  for i in xrange(d2c.size):
   m1 = ntwidth == twidth[i]
   frac = otwidth[m1]/np.sum(otwidth[m1])
   ntwidth[m1] = frac*ntwidth[m1]
   nbwidth[m1] = frac*nbwidth[m1]
  twidth = ntwidth
  bwidth = nbwidth

  #Place the parameters
  hru_properties['hillslope_length'][m] = hlength[idx]
  hru_properties['slope'][m] = slope[idx]
  hru_properties['depth2channel'][m] = helev[idx]
  hru_properties['hillslope_position'][m] = hpos[idx]
  hru_properties['width_top'][m] = twidth[idx]
  hru_properties['width_bottom'][m] = bwidth[idx]

 return hru_properties

