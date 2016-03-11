#!/usr/bin/python

import argparse
import numpy as np, numpy.linalg
import os, sys, math

eps = 10.0**-8.0

# main function
def main():
   
    # get command line
    args = get_command_line()
    prefix = args.prefix
    num_eig = args.k
    out_file = args.out
    gc = args.lambda_gc
    tot_h2g = args.tot_h2g
    sense_thres = args.sense_threshold
    eig_thres = args.eig_threshold

    # load step1
    locus_info,all_eig,all_prj = load_step1(prefix)

    # estimate h2g jointly when total h2g is not provided
    if(tot_h2g is None):
        all_h2g,raw_est = get_local_h2g_joint(locus_info, all_eig,
            all_prj, num_eig, eig_thres, sense_thres, gc)
        all_var = get_var_est_joint(locus_info, all_h2g)
    # estimate h2g independently when total h2g is provided
    else:
        pass

    # write output
    output_local_h2g(out_file, locus_info, raw_est, all_h2g, all_var)

# write to output
def output_local_h2g(out_file, locus_info, raw_est, all_h2g, all_var):
    out_file = open(out_file, 'w')
    out_file.write('chr\tstart\tend\tnum_snp\tk\tlocal_h2g\tvar\n')
    num_win = len(locus_info)
    for i in xrange(num_win):
        line = '%s\t%s\t%s\t%s\t%d\t%.10f\t%.12f' % (
            locus_info[i][0], locus_info[i][1], locus_info[i][2],
            locus_info[i][3], raw_est[i][1], all_h2g[i,0], all_var[i,0])
        out_file.write(line+'\n')
    out_file.close()

# get biased raw estimate
def get_raw_h2g(locus_info, all_eig, all_prj, max_k, eig_thres, gc):
    raw_est = []
    for i in xrange(len(locus_info)):
        k = min(max_k, np.where(all_eig[i] > eig_thres)[0].size)
        tmp = np.divide(all_prj[i][0,0:k], all_eig[i][0,0:k]+eps)
        raw_est.append((np.sum(tmp)*gc, float(k)))
    return raw_est

# estimate local heritability jointly
def get_local_h2g_joint(locus_info, all_eig, all_prj, num_eig,
    eig_thres, sense_thres, gc):
    
    # estimate my gc
    num_win = len(locus_info)
    raw_est = get_raw_h2g(locus_info, all_eig, all_prj, num_eig, eig_thres, 1.0)
    obs_th = []
    for i in xrange(num_win):
        n = float(locus_info[i][5])
        obs_th.append([raw_est[i][0], raw_est[i][1]/(n+eps)])
    obs_th = np.matrix(sorted(obs_th, key=lambda x: x[0]))
    num_use = int(0.5*num_win)
    my_gc = np.linalg.pinv(obs_th[0:num_use,0])*obs_th[0:num_use,1]
    my_gc = max(my_gc[0,0], 1.0)

    # choose max k
    max_k = float(num_eig)
    avg_n = np.mean(np.array([float(elem[5]) for elem in locus_info]))
    for i in reversed(xrange(num_eig+1)):
        denom = avg_n-num_win*max_k
        if(avg_n/denom < sense_thres and denom > 0):
            break
        max_k -= 1.0
    
    # adjust for bias
    raw_est = get_raw_h2g(locus_info, all_eig, all_prj, max_k, eig_thres, my_gc)
    A = np.matrix(np.zeros((num_win, num_win)))
    b = np.matrix(np.zeros((num_win, 1)))
    for i in xrange(num_win):
        n = float(locus_info[i][5])
        for j in xrange(num_win):
            if(i == j):
                A[i,j] = n-raw_est[i][1]
            else:
                A[i,j] = -raw_est[i][1]
        b[i,0] = n*raw_est[i][0]-raw_est[i][1]
    est = np.linalg.pinv(A)*b
    est[np.where(est>0.001)] = 0.001

    print np.sum(est)

    return est,raw_est

# estimate variance when local heritability is estimated jointly
def get_var_est_joint(locus_info, all_h2g):
    num_win = len(locus_info)
    tot = np.sum(all_h2g)
    A = np.matrix(np.zeros((num_win, num_win)))
    b = np.matrix(np.zeros((num_win, 1)))
    for i in xrange(num_win):
        n = float(locus_info[i][5])
        p = float(locus_info[i][4])
        for j in xrange(num_win):
            if(i == j):
                A[i,j] = 1.0
            else:
                A[i,j] = p/(n-p+eps)
                A[i,j] = -A[i,j]*A[i,j]
        b[i,0] = ((n/(n-p+eps))**2.0)
        b[i,0] *= (2.0*p*((1.0-tot)/(n+eps))+4.0*all_h2g[i,0])
        b[i,0] *= ((1.0-tot)/(n+eps))
    var_est = np.linalg.pinv(A)*b
    return var_est

# load step 1
def load_step1(prefix):
    
    # load info
    locus_info = []
    for i in xrange(1,23):
        fnm = '%s_chr%d.info' % (prefix, i)
        if(not os.path.exists(fnm)):
            continue
        fnm = open(fnm)
        for line in fnm:
            line = line.strip()
            cols = line.split()
            locus_info.append((i,cols[0],cols[1],cols[2],cols[3],cols[4]))
        fnm.close()

    # eigs
    all_eig = []
    for i in xrange(1,23):
        fnm = '%s_chr%d.eig' % (prefix, i)
        if(not os.path.exists(fnm)):
            continue
        fnm = open(fnm)
        for line in fnm:
            line = line.strip()
            cols = line.split()
            tmp = np.matrix([float(cols[i]) for i in range(len(cols))])
            all_eig.append(tmp)
        fnm.close()
    
    # prjsq
    all_prj = []
    for i in xrange(1,23):
        fnm = '%s_chr%d.prjsq' % (prefix, i)
        if(not os.path.exists(fnm)):
            continue
        fnm = open(fnm)
        for line in fnm:
            line = line.strip()
            cols = line.split()
            tmp = np.matrix([float(cols[i]) for i in range(len(cols))])
            all_prj.append(tmp)
        fnm.close()
    
    return locus_info,all_eig,all_prj

# get command line
def get_command_line():
    parser = argparse.ArgumentParser(description='Estimate local h2g')
    parser.add_argument('--prefix', dest='prefix', type=str,
                   help='Prefix used for step 1', required=True)
    parser.add_argument('--out', dest='out', type=str,
                   help='Output file name', required=True)
    parser.add_argument('--k', dest='k', type=int, default=50,
                   help='Maximum number of eigenvectors to use (default 50)')
    parser.add_argument('--lambda_gc', dest='lambda_gc', type=float,
                   default=1.0, help='Genomic control factor (default 1.0)')
    parser.add_argument('--tot_h2g', dest='tot_h2g', type=float,
                   help='Total trait SNP heritability')
    parser.add_argument('--sense-threshold', dest='sense_threshold', type=float,
                   default=2.0, help='Sensitivity threshold on \
                   total h2g estimates, used when tot_h2g is not provided \
                   (default 2.0)')
    parser.add_argument('--eig-threshold', dest='eig_threshold', type=float,
                   default=1.0, help='Eigenvalue threshold (default 1.0)')
    args = parser.parse_args()
    return args

if(__name__ == '__main__'):
    main()