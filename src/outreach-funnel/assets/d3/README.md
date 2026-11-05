# Vendored d3 files

`outreach_funnel.py` inlines these two scripts into `index.html`, so the page loads nothing from the network. The files are unchanged copies of the npm packages' builds, downloaded from jsDelivr on Nov. 3, 2026.

| File | Package | Source | SHA-256 |
| --- | --- | --- | --- |
| `d3.min.js` | d3 7.9.0 | <https://cdn.jsdelivr.net/npm/d3@7.9.0/dist/d3.min.js> | `f2094bbf6141b359722c4fe454eb6c4b0f0e42cc10cc7af921fc158fceb86539` |
| `d3-sankey.min.js` | d3-sankey 0.12.3 | <https://cdn.jsdelivr.net/npm/d3-sankey@0.12.3/dist/d3-sankey.min.js> | `8286db5d6aa049cc6e8a546708943b79dfb4daaefb0ccf42af674ec0ee4c86be` |

Licenses, copied from the same packages:

- `d3-LICENSE`: d3, ISC License, from <https://cdn.jsdelivr.net/npm/d3@7.9.0/LICENSE>.
- `d3-sankey-LICENSE`: d3-sankey, BSD 3-Clause License, from <https://cdn.jsdelivr.net/npm/d3-sankey@0.12.3/LICENSE>.

The page repeats both license texts in a comment above each inlined script.

To check a file: `shasum -a 256 d3.min.js d3-sankey.min.js`.
