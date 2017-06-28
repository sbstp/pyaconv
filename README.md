# pyaconv
**pyaconv** is an audio converter based on gstreamer. It can encode music in
lighter formats, useful for streaming and mobile devices. For instance, it can
take a library of FLAC files and encode it into the incredibly efficient OPUS
format.

## Features
* Supports decoding audio from all the formats available in the gstreamer
framework.
* Supports encoding to OPUS [more targets to come].
* Supports multi-thread encoding. By default the number of processors minus one
 is used, or 1 if you have a single processor.
* Incremental encoding is built-in. The process can stopped and restarted at
any time. A journal is kept in the target folder, allowing it to continue where
it left off.
* Other files, such as cover art and cue files are hard linked, saving a little
bit of space.
* The incremental nature of the program makes it ideal for regular use. Only
the new files will be encoded.
