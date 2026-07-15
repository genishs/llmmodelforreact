import React from "react";
import { SERVER_URL } from "@/config";

interface EgovImageGalleryProps {
  boardFiles?: { atchFileId: string; fileSn: number }[];
}

function EgovImageGallery({ boardFiles }: EgovImageGalleryProps) {
  const [filesTag, setFilesTag] = React.useState<JSX.Element[]>([]);

  React.useEffect(() => {
    if (boardFiles !== undefined) {
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
    }
  }, [boardFiles]);

  console.log("filesTag : ", filesTag);

  return <div className="board_attach_img">{filesTag}</div>;
}

export default EgovImageGallery;