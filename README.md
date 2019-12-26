# tile-packager
Packages tiles for offline use given a Style JSON

The idea with this was that I could pass any arbitrary Style JSON file and
create a ZIP file for a given geometry to be used offline.

I discovered, however, that the Mapbox Offline Packs, the standard way to
download offline map tiles in a Mapbox SDK, supports _any Style JSON file_, not
just ones with a `mapbox://` url.

I suppose that should have been obvious in retrospect, that anywhere a
`mapbox://` url is accepted, a third-party Style JSON file will be too, but I
didn't realize it.

Because of that, development on this is paused.