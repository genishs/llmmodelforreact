import React from 'react';

interface BoardFile { fileSn?: string; atchFileId?: string; }

function EgovImageGallery({ boardFiles }: { boardFiles?: BoardFile[] }) {
  const filesTag = boardFiles?.map((item, index) => (
    <React.Fragment key={index}>
      <img
        src={`${process.env.SERVER_URL || ''}/image?atchFileId=${item.atchFileId}&fileSn=${item.fileSn}`}
        alt=""
      />
      <br />
    </React.Fragment>
  ));

  return <div className="board_attach_img">{filesTag}</div>;
}

export default EgovImageGallery;