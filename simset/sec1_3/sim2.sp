

* settings ***************
.lib 'lib/settings.lib' settings
**************************

* opamp ******************
.include 'tmp/opamp.sp'
**************************

* sr *********************
.title sr
.include 'tmp/for_sr.sp'
.lib 'lib/sr.lib' tran1
**************************
