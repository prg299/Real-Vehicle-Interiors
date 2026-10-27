// Reuse an existing clean panel in the optimized f700box wall atlas. Mirrored
// sampling preserves its grain without crossing the authored dark grooves.
// The native hull and authored partition use this identical material mapping.
uniform float MELensSeamlessWall;

vec2 meLensUnseamedWallUV(vec2 uv)
{
    if(MELensSeamlessWall<0.5 || uv.x<0.5 || uv.x>0.98 || uv.y<0.099 || uv.y>0.981)return uv;
    float phase=1.0-abs(2.0*fract(uv.x*30.0)-1.0);
    uv.x=mix(0.5083333333,0.525,phase);
    return uv;
}
