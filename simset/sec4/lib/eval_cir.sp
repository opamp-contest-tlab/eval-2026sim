*
*
* (a)
.subckt eval_cir in out vdd vss
X1	inm inp out vdd vss	opamp
R1	in inm	rf1
R2	inm out	rf2
R3	in inp	rf1
R4	inp 0	rf1
* rl
RL	out 0	rl
CL	out 0	cl
.ends


.PARAM 
+ rl=20k            			$ load resistance
+ cl=1n              			$ load capacitance
+ rf=1T cf=10m				$ open loop feedback
+ rf1=20k rf2=220k			$ feedback resistance
+ Gain='(rf2 - rf1)/(2 * rf1)'	$ gain
+ rl_open='(rl*(rf1+rf2))/(rl+rf1+rf2)'	$ open loop load resistance 