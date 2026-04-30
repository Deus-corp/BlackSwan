#!/bin/bash
cd docs/book
mdbook build
cd ../..
git branch -D gh-pages 2>/dev/null
git checkout --orphan gh-pages
git rm -rf .
cp -r docs/book/book/* .
touch .nojekyll
git add -A
git commit -m "Site deploy $(date +%Y-%m-%d_%H:%M)"
git push origin gh-pages --force
git checkout main