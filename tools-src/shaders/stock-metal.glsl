// Stock painted metal uses existing game pixels and the live vehicle's paint.
// Native and authored structural faces share this colour and physical projection.
uniform sampler2D MELensStockPaintTexture;
uniform sampler2D MELensStockPanelTexture;
uniform vec4 MELensStockMetal;  // mesh scale, panel width, panel height, enabled
uniform vec4 MELensStockPaint;  // live paint sampler UV, random-paint flag, unused
uniform vec4 MELensStockPanel;  // inset native panel sampler UV bounds
uniform vec4 MELensStockHSV;    // native root painColor, unused
uniform vec4 MELensStockOrigin; // continuous passenger X/Z origin, body floor dot, unused

vec3 meLensStockPaint(vec3 colour, vec3 paint)
{
    float high = max(colour.r, max(colour.g, colour.b));
    float low = min(colour.r, min(colour.g, colour.b));
    float saturation = high > 0.0 ? (high - low) / high : 0.0;
    saturation = clamp(saturation + paint.y - 0.5, 0.0, 0.9999);
    float value = clamp(high + paint.z - 0.5, 0.0, 0.9999);
    vec3 hue = clamp(abs(mod(fract(paint.x) * 6.0 + vec3(0.0, 4.0, 2.0), 6.0) - 3.0) - 1.0, 0.0, 1.0);
    return value * mix(vec3(1.0), hue, saturation);
}

vec3 meLensStockMetalColour(vec3 p, vec3 up)
{
    float along = (-p.x + p.y) * MELensStockMetal.x
        - MELensStockOrigin.x - MELensStockOrigin.y;
    float u = fract(along / max(MELensStockMetal.y, 0.001));
    float h = (dot(p, up) - MELensStockOrigin.z) * MELensStockMetal.x;
    float v = clamp(h / max(MELensStockMetal.z, 0.001), 0.0, 1.0);
    // These are the game's PNG sampler coordinates; do not flip the bounds again.
    vec2 uv = mix(MELensStockPanel.xy, MELensStockPanel.zw, vec2(u, 1.0-v));
    vec3 panel = texture2D(MELensStockPanelTexture, uv).rgb;
    vec3 reference = texture2D(MELensStockPanelTexture, vec2(0.56640625, 0.35546875)).rgb;
    vec3 luma = vec3(0.299, 0.587, 0.114);
    float detail = clamp(dot(panel, luma) / max(dot(reference, luma), 0.001), 0.25, 1.15);
    vec4 live = texture2D(MELensStockPaintTexture, MELensStockPaint.xy);
    // Resolve the exact stock HSV/alpha paint once, then keep the panel's pressed shading.
    float paintAmount = (1.0-live.a) * MELensStockPaint.z;
    vec3 colour = mix(live.rgb, meLensStockPaint(live.rgb, MELensStockHSV.xyz), paintAmount);
    // Interior diffuse light must still reveal pressed metal on near-black paint.
    // Preserve the resolved hue where it exists; zero-value paint uses charcoal.
    float high = max(colour.r, max(colour.g, colour.b));
    if (high < 0.26)
        colour = high > 0.001 ? colour * (0.26 / high) : vec3(0.26);
    return min(max(colour * detail, vec3(0.0)), vec3(1.0));
}
