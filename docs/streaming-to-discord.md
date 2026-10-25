# Share the Frame view in Discord

1. Start the **OBS source** in Frame Control and add it to OBS as described in
   [Headset view in OBS](obs-headset-source.md). Confirm that OBS shows the
   headset mirror and that its audio meter moves before joining a call.
2. In OBS, click **Start Virtual Camera**. In Discord's **Voice & Video**
   settings, select **OBS Virtual Camera** as the camera, then turn it on in the
   call. This sends the OBS scene as video.
3. If the call needs the Frame's game sound, route OBS's monitored Media Source
   audio to a virtual audio input installed on your computer, then select that
   input as Discord's microphone. Keep headphones on to avoid feedback. Test
   this in a private call first; a virtual camera alone carries no audio.
4. Stop the OBS source in Frame Control when you finish. It closes the SSH
   stream; OBS may keep showing its last frame until the source is hidden.

Frame Control sends the Frame's **output audio**, not its microphone. Discord
audio routing differs by computer and requires a separate virtual audio device
if you want game sound in the call. This guide has not been verified in a real
Discord call. The SteamVR mirror can be blank while the headset is idle, and
the mirror can include real room passthrough behind panels. Check the scene before sharing.
