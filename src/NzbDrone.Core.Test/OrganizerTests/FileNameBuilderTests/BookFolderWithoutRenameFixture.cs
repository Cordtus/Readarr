using System.Collections.Generic;
using System.IO;
using System.Linq;
using FizzWare.NBuilder;
using FluentAssertions;
using NUnit.Framework;
using NzbDrone.Core.Books;
using NzbDrone.Core.CustomFormats;
using NzbDrone.Core.MediaFiles;
using NzbDrone.Core.Organizer;
using NzbDrone.Core.Qualities;
using NzbDrone.Core.Test.Framework;
using NzbDrone.Test.Common;

namespace NzbDrone.Core.Test.OrganizerTests.FileNameBuilderTests
{
    [TestFixture]
    public class BookFolderWithoutRenameFixture : CoreTest<FileNameBuilder>
    {
        private Author _author;
        private Edition _edition;
        private BookFile _bookFile;
        private NamingConfig _namingConfig;

        [SetUp]
        public void Setup()
        {
            _author = Builder<Author>
                .CreateNew()
                .With(s => s.Name = "Brandon Sanderson")
                .With(s => s.Path = @"C:\Test\Brandon Sanderson".AsOsAgnostic())
                .With(s => s.Metadata = new AuthorMetadata { Name = "Brandon Sanderson" })
                .Build();

            var book = Builder<Book>
                .CreateNew()
                .With(s => s.Title = "Rhythm of War")
                .With(s => s.AuthorMetadata = _author.Metadata.Value)
                .With(s => s.SeriesLinks = new List<SeriesBookLink>())
                .Build();

            _edition = Builder<Edition>
                .CreateNew()
                .With(s => s.Title = book.Title)
                .With(s => s.Book = book)
                .Build();

            _namingConfig = NamingConfig.Default;
            _namingConfig.RenameBooks = false;

            Mocker.GetMock<INamingConfigService>()
                .Setup(c => c.GetConfig()).Returns(_namingConfig);

            _bookFile = Builder<BookFile>.CreateNew()
                .With(e => e.Path = @"C:\Downloads\STORMLIGHT0401P01.mp3".AsOsAgnostic())
                .With(e => e.Part = 1)
                .With(e => e.PartCount = 39)
                .With(e => e.Quality = new QualityModel(Quality.MP3))
                .Build();

            Mocker.GetMock<IQualityDefinitionService>()
                .Setup(v => v.Get(Moq.It.IsAny<Quality>()))
                .Returns<Quality>(v => Quality.DefaultQualityDefinitions.First(c => c.Quality == v));

            Mocker.GetMock<ICustomFormatService>()
                .Setup(v => v.All())
                .Returns(new List<CustomFormat>());
        }

        [Test]
        public void should_keep_the_original_name_inside_the_book_folder_when_rename_is_off()
        {
            Subject.BuildBookFileName(_author, _edition, _bookFile)
                .Should().Be(Path.Combine("Rhythm of War", "STORMLIGHT0401P01").AsOsAgnostic());
        }

        [Test]
        public void should_build_the_full_path_inside_the_book_folder()
        {
            var name = Subject.BuildBookFileName(_author, _edition, _bookFile);

            Subject.BuildBookFilePath(_author, _edition, name, ".mp3")
                .Should().Be(@"C:\Test\Brandon Sanderson\Rhythm of War\STORMLIGHT0401P01.mp3".AsOsAgnostic());
        }

        [Test]
        public void should_not_add_a_folder_when_the_pattern_has_none()
        {
            _namingConfig.StandardBookFormat = "{Author Name} - {Book Title}";

            Subject.BuildBookFileName(_author, _edition, _bookFile)
                .Should().Be("STORMLIGHT0401P01");
        }

        [Test]
        public void should_use_the_original_name_when_the_pattern_is_empty()
        {
            _namingConfig.StandardBookFormat = string.Empty;

            Subject.BuildBookFileName(_author, _edition, _bookFile)
                .Should().Be("STORMLIGHT0401P01");
        }
    }
}
