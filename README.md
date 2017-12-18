# pyaconv
**pyaconv** is an audio converter based on gstreamer. It can encode music in
lighter formats, useful for streaming and mobile devices. For instance, it can
take a library of FLAC files and encode it into the incredibly efficient OPUS
format.

## Features
* Supports decoding audio from all the formats available in the gstreamer
framework.
* Supports encoding to Opus, MP3 and FLAC.
* Supports multi-core encoding. By default the number of processors minus one
 is used, or 1 if you have a single processor.
* Incremental encoding is built-in. The process can stopped and restarted at
any time. A journal is kept in the target folder, allowing it to continue where
it left off. The encoding settings are saved for each audio file, permitting
pyaconv to know when it should overwrite existing files.
* Other files, such as cover art and cue files are hard linked, saving a little
bit of space. If they're located on a different filesystem, they're copied.
* The interactive mode lets you select folders to encode interactively. The
selection process can be stopped and resumed, previous selection are remembered.

## Examples
Encode a directory to opus at 64kbit/s
```
pyaconv -c opus --bitrate 64000 ~/share/music/ music.opus
```

Select folders to encode using the interactive mode
```
pyaconv -c mp3 --quality 2 -i ~/share/music/ music.mp3
...
Include Air? [y/n]: y
Include Bonobo? [y/n]: y
....
```
