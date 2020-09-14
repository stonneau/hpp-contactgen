print "Plan guide trajectory ..."
import lp_urdfs_path as tp # change here to try different demo
print "Guide planned."

from sl1m.rbprm.surfaces_from_path import *
from sl1m.constants_and_tools import *
from sl1m.problem_definition import *

# from sl1m.planner import *
# from sl1m.tools.plot_plytopes import *
from sl1m.planner_scenarios.talos.constraints import *

def footPosFromCOM(init_com):
    lf_0 = array(init_com[0:3]) + array([0, 0.085,-0.98])
    rf_0 = array(init_com[0:3]) + array([0,-0.085,-0.98])
    return [lf_0,rf_0]
    

def gen_pb(init, s_p0, goal, R, surfaces):
    
    nphases = len(surfaces)
    kinematicConstraints = genKinematicConstraints(left_foot_constraints, right_foot_constraints)
    relativeConstraints = genFootRelativeConstraints(right_foot_in_lf_frame_constraints, left_foot_in_rf_frame_constraints)    
    res = { "p0" : init, "c0" : s_p0, "goal" : goal, "nphases": nphases}
    #res = { "p0" : None, "c0" : None, "goal" : None, "nphases": nphases}
    
    #TODO in non planar cases, K must be rotated
    # phaseData = [ {"moving" : i%2, "fixed" : (i+1) % 2 , "K" : [copyKin(kinematicConstraints) for _ in range(len(surfaces[i]))], "relativeK" : [relativeConstraints[(i)%2] for _ in range(len(surfaces[i]))], "S" : surfaces[i] } for i in range(nphases)]
    phaseData = [ {"moving" : i%2, "fixed" : (i+1) % 2 , "K" : [genKinematicConstraints(left_foot_constraints,right_foot_constraints,index = i, rotation = R, min_height = 0.3) for _ in range(len(surfaces[i]))], "relativeK" : [genFootRelativeConstraints(right_foot_in_lf_frame_constraints,left_foot_in_rf_frame_constraints,index = i, rotation = R)[(i) % 2] for _ in range(len(surfaces[i]))], "rootOrientation" : R[i], "S" : surfaces[i] } for i in range(nphases)]
    res ["phaseData"] = phaseData
    return res 
    
import mpl_toolkits.mplot3d as a3
import matplotlib.colors as colors
import matplotlib.pylab as plt
import scipy as sp
import numpy as np

all_surfaces = []

def draw_rectangle(l, ax):
    #~ plotPoints(ax,l)
    l = l[0]
    lr = l + [l[0]]
    cx = [c[0] for c in lr]
    cy = [c[1] for c in lr]
    cz = [c[2] for c in lr]
    ax.plot(cx, cy, cz)

def plotSurface (points, ax, color_id = -1):
    xs = np.append(points[0,:] ,points[0,0] ).tolist()
    ys = np.append(points[1,:] ,points[1,0] ).tolist()
    zs = (np.append(points[2,:] ,points[2,0] ) - np.ones(len(xs))*0.005*color_id).tolist()
    colors = ['r','g','b','m','y','c']
    if color_id == -1: ax.plot(xs,ys,zs,'black')
    else: ax.plot(xs,ys,zs,colors[color_id])

def draw_scene(surfaces, ax = None):
    if ax is None:        
        fig = plt.figure()
        ax = fig.add_subplot(111, projection="3d")
    for surface in surfaces[0]:
        plotSurface(surface, ax)
    plt.ion()
    return ax  
        
def draw_contacts(surfaces, ax = None):
    colors = ['r','g','b','m','y','c']
    color_id = 0
    if ax is None:        
        fig = plt.figure()
        ax = fig.add_subplot(111, projection="3d")
    # [draw_rectangle(l,ax) for l in all_surfaces]
    for surfaces_phase in surfaces: 
      for surface in surfaces_phase:
        plotSurface(surface, ax, color_id)
      color_id += 1
      if color_id >= len(colors):
        color_id = 0
    plt.ion()
    return ax    

import pickle

def readFromFile (fileName):
  data = []
  try:
      with open(fileName,'rb') as f:
        while True:
          try:
            line = pickle.load(f)
          except EOFError:
            break
          data.append(line)  
  except:
      return None
  return data[0]
  

fileName = "data/comptime/optimization/cpp/"+tp.pbName+"_MIP"

data = readFromFile(fileName)
    
if data != None:
    comptime = data[0]
    # iterations = data[1]
else :    
    comptime = []
    # iterations = []


#### MPC-style
def getDist (waypoint1, waypoint2):
    return np.power(waypoint2[0] - waypoint1[0],2) + np.power(waypoint2[1] - waypoint1[1],2) + np.power(waypoint2[2] - waypoint1[2],2)
    
def getSelectedSurfaces (res, surfaces, l = []):
    for i in range(NUM_STEP):
        for j in range(len(surfaces[0])):
            index = i*(pl1.NUM_SLACK_PER_SURFACE*len(surfaces[0])+4) +4 + j*pl1.NUM_SLACK_PER_SURFACE
            if (res[index] <= 0.01 and j not in l):
                l.append(j)
    return l

step_size = 0.5
DISCRETIZE_SIZE = 0.1
EPSILON = 1.0
NUM_STEP = 4

from sl1m.fix_sparsity import solveL1,solveL1_re,solveL1_cost,solveL1_cost_re,solveMIP,solveMIP_cost
import sl1m.planner   as pl
import sl1m.planner_l1   as pl1

configs = getConfigsFromPath (tp.ps, tp.pathId, step_size)
surfaces_dict = getAllSurfacesDict(tp.afftool)
all_surfaces = getAllSurfaces(tp.afftool)   

s_p0 = configs[0][0:3]; init = footPosFromCOM(s_p0)
g_p0 = configs[-1][0:3]; goal = footPosFromCOM(g_p0)
R, surfaces = getSurfacesFromPath_mpc(tp.rbprmBuilder, configs, surfaces_dict, NUM_STEP, tp.v, False)

PLOT = False
MIP = True
LINEAR = False
CPP = True
WSLACK = True
i = 0
dist = getDist(s_p0,g_p0)
OPT = (len(surfaces[0])-1)*NUM_STEP
weight = 0.01
tot_time = 0.; tot_iter = 0.
loop = 0

while getDist(init[0],goal[0]) > EPSILON :
    if i == 5:
        break
        
    #weight = 10.*i/len(surfaces[0])
    print i,"th iteration, weight:", weight
    
    pb = gen_pb(init, s_p0, goal, R, surfaces)

    if MIP:
        pb, res, time = solveMIP_cost(pb, surfaces, True, draw_scene, PLOT, CPP, WSLACK, LINEAR)
        print "time to solve MIP: ", time
        coms, footpos, allfeetpos = pl1.retrieve_points_from_res(pb, res)
    else:
        pb, res, time= solveL1_cost(pb, surfaces, draw_scene, PLOT, CPP, weight, LINEAR)
        # pb, res, time, iteration= solveL1_cost_re(pb, surfaces, draw_scene, PLOT, CPP, weight, LINEAR)
        time_ = 0.
        if type(res) == int:
            weight = 0.
            pb = gen_pb(init, s_p0, goal, R, surfaces)
            pb, res, time_ = solveL1_cost(pb, surfaces, draw_scene, PLOT, CPP, weight, LINEAR)    
            # pb, res, time_ , iteration= solveL1_cost_re(pb, surfaces, draw_scene, PLOT, CPP, weight, LINEAR)    
            time += time_
        print "time to solve LP: ", time+time_
        coms, footpos, allfeetpos = pl1.retrieve_points_from_res(pb, res)
        
    i += 1
    tot_time += time
    # tot_iter += iteration

    init = [allfeetpos[-1-((NUM_STEP+1)%2)],allfeetpos[-1-((NUM_STEP)%2)]]
    s_p0 = coms[-1]
    dist = getDist(s_p0,g_p0)
    
    weight = 1000./(dist*OPT)
    
    if dist <= 5.0:
        weight = 50.
    
    # print s_p0, dist

comptime += [tot_time]
# iterations += [tot_iter]
data = [comptime]#, iterations]
print tot_time

with open(fileName,'wb') as f:
    pickle.dump(data,f)

"""
data = readFromFile("data/comptime/optimization/cpp/rubbles_2_MIP")
comptime = data[0]
# iterations = data[1]

len(comptime)
sum(comptime)/len(comptime)
# sum(iterations)
"""