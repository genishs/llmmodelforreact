import React from "react";
import { SERVER_URL } from "@/config";

interface BoardFile {
  atchFileId: string;
  fileSn: number;
}

interface EgovImageGalleryProps {
  boardFiles?: BoardFile[];
}

function EgovImageGallery({ boardFiles }: EgovImageGalleryProps): JSX.Element {
  const [filesTag, setFilesTag] = React.useState<JSX.Element[]>([]);

  React.useEffect(() => {
    if (boardFiles === undefined) return;

    const tags: JSX.Element[] = [];
    boardFiles.forEach((item, index) => {
      tags.push(
        <React.Fragment key={index}>
          <img
            src={`${SERVER_URL}/image?atchFileId=${item.atchFileId}&fileSn=${item.fileSn}`}
            alt=""
          />
          <br />
        </React.Fragment>
      );
    });

    setFilesTag(tags);
  }, [boardFiles]);

  return <div className="board_attach_img">{filesTag}</div>;
}

export default EgovImageGallery;