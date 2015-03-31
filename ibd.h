#ifndef IBD_H_INCLUDED
#define IBD_H_INCLUDED

#include <iostream>
#include <fstream>
#include <iterator>
#include <cstdio>
#include <cstdint>
#include <cmath>
#include <vector>
#include <algorithm>
#include <assert.h>
#include "polylog/polylog.h"
#include <gsl/gsl_math.h>
#include <gsl/gsl_sf_bessel.h>
#include <gsl/gsl_sf_gamma.h>
#include <numeric>


using namespace std;

class IBD
{
private:
	

	double s;
	double ss; 
	double u;
	int ndc;
	vector<int> data;
	vector<int> sz;
	vector<double> dist;
	vector<double> plog;
	double fhat;
	double ne;
	double a;
	double de;
	double z;
	double sqrz;
	double g0;
	float tsz;
	int ntt;
	int split;
	double cml();
	double t_series(double x);
	double bessel(double x);

public:
	void initialize(double mu, int num_t_series_terms, vector<int> &dataIn, vector<double> &distIn, vector<int> &szIn);
	double update(double sigma_i, double de_i);
};

/*
static double PLOG[30] = {
8.5172931897496280,
1.6430306182100543,
1.2017281166907554,
1.0820828552153867,
1.0367113145355733,
1.0171356980782826,
1.0081458295066380,
1.0038757066879467,
1.0018075975204717,
1.0007941935294555,
1.0002940097279232,
1.0000460077341429,
0.9999226841388169,
0.9998612435959770,
0.9998305959878008,
0.9998152961416530,
0.9998076541404645,
0.9998038357647978,
0.9998019274480775,
0.9998009735791344,
0.9998004967408992,
0.9998002583538018,
0.9998001391709121,
0.9998000795830166,
0.9998000497902509,
0.9998000348942621,
0.9998000274463988,
0.9998000237225109,
0.9998000218605815,
0.9998000209296217,
};
*/
#endif // IBD_H_INCLUDED