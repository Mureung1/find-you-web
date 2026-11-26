import Image from "next/image";
import styles from "./management.module.css";

export function PrivatePhotos({ itemId, positions, removing, onRemove }: {
  itemId: string;
  positions: number[];
  removing?: boolean;
  onRemove?: (position: number) => void;
}) {
  if (!positions.length) return null;
  return (
    <ul className={styles.photoList} aria-label="비공개 습득물 사진">
      {positions.map((position, index) => {
        const path = `/api/my/items/${encodeURIComponent(itemId)}/photos/${position}`;
        return (
          <li key={position}>
            <a href={path} aria-label={`습득물 사진 ${index + 1} 크게 보기`}>
              <Image src={path} alt={`습득물 사진 ${index + 1}`} width={160} height={120} unoptimized />
            </a>
            {onRemove && <button type="button" className="text-button" disabled={removing}
              onClick={() => onRemove(position)}>사진 {index + 1} 삭제</button>}
          </li>
        );
      })}
    </ul>
  );
}
