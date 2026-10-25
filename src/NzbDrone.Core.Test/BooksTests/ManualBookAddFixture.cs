using System.Collections.Generic;
using FluentAssertions;
using Moq;
using NUnit.Framework;
using NzbDrone.Core.Books;
using NzbDrone.Core.Exceptions;
using NzbDrone.Core.MetadataSource;
using NzbDrone.Core.Test.Framework;

namespace NzbDrone.Core.Test.BooksTests
{
    [TestFixture]
    public class AddBookServiceFixture : CoreTest<AddBookService>
    {
        private Book ManualBook()
        {
            return new Book
            {
                AuthorMetadataId = 1,
                AuthorMetadata = new AuthorMetadata { ForeignAuthorId = "author-1", Name = "Test Author" },
                Author = new Author { Id = 1, AuthorMetadataId = 1 },
                ForeignBookId = "manual-test",
                Title = "Test Book",
                TitleSlug = "test-book",
                CleanTitle = "testbook",
                Editions = new List<Edition>
                {
                    new Edition
                    {
                        ForeignEditionId = "manual-test",
                        Title = "Test Book",
                        TitleSlug = "test-book"
                    }
                }
            };
        }

        [Test]
        public void should_add_a_manual_book_without_metadata_lookup()
        {
            var book = ManualBook();

            Subject.AddManualBook(book);

            Mocker.GetMock<IProvideBookInfo>()
                .Verify(v => v.GetBookInfo(It.IsAny<string>()), Times.Never);
            Mocker.GetMock<IBookService>()
                .Verify(v => v.AddBook(book, false), Times.Once);
            book.AddOptions.AddType.Should().Be(BookAddType.Manual);
            book.Editions.Value.Should().ContainSingle();
            book.Editions.Value[0].Monitored.Should().BeTrue();
            book.Editions.Value[0].ManualAdd.Should().BeTrue();
        }

        [Test]
        public void should_reject_a_manual_book_without_author_metadata()
        {
            var book = ManualBook();
            book.AuthorMetadataId = 0;

            Assert.Throws<System.InvalidOperationException>(() => Subject.AddManualBook(book));
        }
    }

    [TestFixture]
    public class RefreshBookServiceManualFixture : CoreTest<RefreshBookService>
    {
        [Test]
        public void should_leave_a_manual_book_in_place_when_metadata_has_no_record()
        {
            var book = new Book
            {
                Id = 1,
                AuthorMetadataId = 1,
                ForeignBookId = "manual-test",
                Title = "Test Book",
                AddOptions = new AddBookOptions { AddType = BookAddType.Manual }
            };

            Mocker.GetMock<IProvideBookInfo>()
                .Setup(v => v.GetBookInfo("manual-test"))
                .Throws(new BookNotFoundException("manual-test"));

            var refreshed = Subject.RefreshBookInfo(book);

            refreshed.Should().BeFalse();
            Mocker.GetMock<IBookService>()
                .Verify(v => v.DeleteBook(It.IsAny<int>(), It.IsAny<bool>(), It.IsAny<bool>()), Times.Never);
        }
    }
}
