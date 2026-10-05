// What SdFat wants from Arduino when it is built on the Mac (force-included; the library's sources are not changed).
#ifndef HOST_SHIM_H
#define HOST_SHIM_H
#include <stdint.h>
#include <stddef.h>
#ifdef __cplusplus
class __FlashStringHelper;
extern "C" {
#endif
unsigned long millis(void);
#ifdef __cplusplus
}
#endif
#endif
