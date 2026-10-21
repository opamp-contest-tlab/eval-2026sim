

* settings ***************
.lib 'lib/settings.lib' settings
**************************

* opamp ******************
.include 'tmp/opamp.sp'
**************************

* dc1 ********************
.title dc1
.lib 'lib/dc1.lib' dc1
**************************

* tf1 ********************
.alter tf1
.del lib 'lib/dc1.lib' dc1
.lib 'lib/tf1.lib' tf1
**************************

* ac1 ********************
.alter ac1
.del lib 'lib/tf1.lib' tf1
.lib 'lib/ac1.lib' ac1
**************************

* ac2 ********************
.alter ac2
.del lib 'lib/ac1.lib' ac1
.lib 'lib/ac2.lib' ac2
**************************

* dc2 ********************
.alter dc2
.del lib 'lib/ac2.lib' ac2
.lib 'lib/dc2.lib' dc2
**************************

* tran1 ******************
.alter tran1
.del lib 'lib/dc2.lib' dc2
.lib 'lib/tran1.lib' tran1
**************************

* ac3 ********************
.alter ac3
.del lib 'lib/tran1.lib' tran1
.lib 'lib/ac3.lib' ac3
**************************

* ac4 ********************
.alter ac4
.del lib 'lib/ac3.lib' ac3
.lib 'lib/ac4.lib' ac4
**************************

* dc3 ********************
.alter dc3
.del lib 'lib/ac4.lib' ac4
.lib 'lib/dc3.lib' dc3
**************************

* dc4 ********************
.alter dc4
.del lib 'lib/dc3.lib' dc3
.lib 'lib/dc4.lib' dc4
**************************

* srdc ********************
.alter srdc
.del lib 'lib/dc4.lib' dc4
.lib 'lib/srdc.lib' srdc
**************************
