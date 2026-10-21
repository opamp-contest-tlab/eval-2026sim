

* settings ***************
.include 'lib/settings.lib'
**************************

* opamp ******************
.include 'tmp/opamp.sp'
**************************

* ac1 ********************
.title ac1
.lib 'lib/analyses.lib' ac1
**************************

* ac2 ********************
.alter ac2
.del lib 'lib/analyses.lib' ac1
.lib 'lib/analyses.lib' ac2
**************************

* dc *********************
.alter dc
.del lib 'lib/analyses.lib' ac2
.lib 'lib/analyses.lib' dc
**************************

* tran1 ********************
.alter tran1
.del lib 'lib/analyses.lib' dc
.lib 'lib/analyses.lib' tran1
**************************

* * tran2 ********************
.alter tran2
.del lib 'lib/analyses.lib' tran1
.lib 'lib/analyses.lib' tran2
* **************************
