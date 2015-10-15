#!/bin/sh -f
#PBS -N bb_5gas_test
#PBS -m abe
#PBS -l nodes=24
#PBS -l pmem=4gb
#PBS -l walltime=168:00:00
#PBS -k oe
#PBS -q main
export OMP_NUM_THREADS=24
export PYTHONPATH=/soft/python/lib/python2.7/site-packages/

time_start=`date '+%T%t%d_%h_06'`
  
echo ------------------------------------------------------
echo -n 'Job is running on node '; cat $PBS_NODEFILE
echo ------------------------------------------------------
echo PBS: qsub is running on $PBS_O_HOST
echo PBS: originating queue is $PBS_O_QUEUE
echo PBS: executing queue is $PBS_QUEUE
echo PBS: working directory is $PBS_O_WORKDIR
echo PBS: execution mode is $PBS_ENVIRONMENT
echo PBS: job identifier is $PBS_JOBID
echo PBS: job name is $PBS_JOBNAME
echo PBS: node file is $PBS_NODEFILE
echo PBS: current home directory is $PBS_O_HOME
echo PBS: PATH = $PBS_O_PATH
echo ------------------------------------------------------

module unload mpich2-x86_64
module load mvapich2

cd /home/bb/retrievals/code
export PATH=/home/bb/retrievals/code:${PATH}    

/usr/local/bin/mpiexec -np 24 python brewster.py 

time_end=`date '+%T%t%d_%h_06'`
echo Started at: $time_start
echo Ended at: $time_end
echo ------------------------------------------------------
echo Job ends
