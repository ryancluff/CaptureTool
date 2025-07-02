# Setup

apt install libhidapi-hidraw0

### /etc/udev/rules.d/99-hidraw.rules
```KERNEL=="hidraw*", ATTRS{idVendor}=="0fd9", ATTRS{idProduct}=="00b9", MODE="0666", GROUP="plugdev", TAG+="uaccess", TAG+="udev-acl"```