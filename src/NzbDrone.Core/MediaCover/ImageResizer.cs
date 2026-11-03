using System;
using System.IO;
using NetVips;
using NzbDrone.Common.Disk;
using NzbDrone.Common.EnvironmentInfo;

namespace NzbDrone.Core.MediaCover
{
    public interface IImageResizer
    {
        void Resize(string source, string destination, int height);
    }

    public class ImageResizer : IImageResizer
    {
        private const int JpegQuality = 92;

        private readonly IDiskProvider _diskProvider;
        private readonly bool _enabled;

        public ImageResizer(IDiskProvider diskProvider, IPlatformInfo platformInfo)
        {
            _diskProvider = diskProvider;

            _enabled = true;
        }

        public void Resize(string source, string destination, int height)
        {
            if (!_enabled)
            {
                return;
            }

            try
            {
                using var image = Image.NewFromFile(source);
                using var resized = image.Resize((double)height / image.Height);

                if (IsJpeg(destination))
                {
                    resized.WriteToFile(destination, new VOption { { "Q", JpegQuality } });
                }
                else
                {
                    resized.WriteToFile(destination);
                }
            }
            catch
            {
                if (_diskProvider.FileExists(destination))
                {
                    _diskProvider.DeleteFile(destination);
                }

                throw;
            }
        }

        private static bool IsJpeg(string path)
        {
            return string.Equals(Path.GetExtension(path), ".jpg", StringComparison.OrdinalIgnoreCase) ||
                   string.Equals(Path.GetExtension(path), ".jpeg", StringComparison.OrdinalIgnoreCase);
        }
    }
}
