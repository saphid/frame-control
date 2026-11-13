/* A stand-in for SteamVR's libopenvr_api.so, for the Frame simulator only.
 *
 * It has just what ui/frame_vrshot.py calls through ctypes: VR_InitInternal2,
 * VR_GetGenericInterface("FnTable:IVRScreenshots_001"), VR_ShutdownInternal,
 * and the screenshot table's RequestScreenshot. A stereo screenshot runs
 * /usr/local/lib/fakeframe/sim/scene.py, which writes the side-by-side PNG and
 * then the left-eye preview, in the order the compositor does (frame_vrshot.py,
 * verified 2026-09-25, SteamVR 2.17.10). Any other interface is "not found",
 * so callers fail the way they would with an older SteamVR.
 *
 * "SteamVR off" (frame-sim-ctl vr off) answers init error 121,
 * VRInitError_Init_NoServerForBackgroundApp, as an overlay app gets when
 * vrserver isn't running. Error numbers are from openvr_capi.h.
 */
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <sys/wait.h>
#include <unistd.h>

#define SCENE "/usr/local/lib/fakeframe/sim/scene.py"
#define VR_OFF "/var/lib/fakeframe/sim/vr-off"

typedef int Err;
typedef uint32_t Handle;

static Err request_screenshot(Handle *handle, int type, const char *preview, const char *vr) {
    static Handle next = 1;
    char stereo[4096], left[4096];
    if (type != 2 || !preview || !vr)            /* only stereo, as frame_vrshot.py asks */
        return 1;                                /* VRScreenshotError_RequestFailed */
    if (snprintf(stereo, sizeof stereo, "%s.png", vr) >= (int)sizeof stereo ||
        snprintf(left, sizeof left, "%s.png", preview) >= (int)sizeof left)
        return 1;
    pid_t pid = fork();
    if (pid < 0)
        return 1;
    if (pid == 0) {
        execl("/usr/bin/python3", "python3", SCENE, "screenshot", stereo, left, (char *)NULL);
        _exit(127);
    }
    int status = 0;
    if (waitpid(pid, &status, 0) < 0 || !WIFEXITED(status) || WEXITSTATUS(status))
        return 1;
    *handle = next++;
    return 0;
}

static Err unsupported(void) { return 1; }

/* VR_IVRScreenshots_FnTable (IVRScreenshots_001): seven entries, RequestScreenshot first. */
static void *screenshots[7] = {
    (void *)request_screenshot, (void *)unsupported, (void *)unsupported, (void *)unsupported,
    (void *)unsupported, (void *)unsupported, (void *)unsupported,
};

uint32_t VR_InitInternal2(Err *err, int type, const char *startup) {
    (void)type; (void)startup;
    if (access(VR_OFF, F_OK) == 0) {
        *err = 121;
        return 0;
    }
    *err = 0;
    return 1;
}

void *VR_GetGenericInterface(const char *version, Err *err) {
    if (version && strcmp(version, "FnTable:IVRScreenshots_001") == 0) {
        *err = 0;
        return screenshots;
    }
    *err = 105;                                  /* VRInitError_Init_InterfaceNotFound */
    return NULL;
}

void VR_ShutdownInternal(void) {}
