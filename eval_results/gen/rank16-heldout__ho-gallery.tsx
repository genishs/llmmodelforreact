import React from 'react';

interface EgovImageGalleryProps {
  boardFiles?: { atchFileId: string; fileSn: number }[];
}

const EgovImageGallery: React.FC<EgovImageGalleryProps> = ({ boardFiles }) => {
  const [filesTag, setFilesTag] = React.useState<JSX.Element[]>([]);

  React.useEffect(() => {
    if (!boardFiles) return;
    const tags = boardFiles.map((item, index) => (
      <React.Fragment key={index}>
        <img
          src={`${SERVER_URL}/image?atchFileId=${item.atchFileId}&fileSn=${item.fileSn}`}
          alt=""
        />
        <br />
      </React.Fragment>
    ));
    setFilesTag(tags);
  }, [boardFiles]);

  return <div className="board_attach_img">{filesTag}</div>;
};

export default EgovImageGallery;